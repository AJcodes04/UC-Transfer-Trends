/**
 * courseMatch.js — course matching and requirement satisfaction logic
 *
 * SCHEMA SUPPORT:
 *   This file handles BOTH the old and new JSON schemas so the frontend keeps
 *   working during the re-scrape transition.
 *
 *   Old format (pre-rewrite):
 *     agreement.sections[].rows[]   (flat ArticulationRow list)
 *
 *   New format (post-rewrite):
 *     agreement.sections[].groups[].options[].rows[]
 *     Each group has: group_logic ("COMPLETE_ALL" | "SELECT_ONE" | "SELECT_N")
 *                     select_n (int, for SELECT_N)
 *                     options[].rows[]
 *
 * GROUP LOGIC SEMANTICS:
 *   COMPLETE_ALL  — Every row's sending_courses must be satisfied.
 *   SELECT_ONE    — Any one complete option (all rows in that option satisfied)
 *                   counts as satisfied. Example: "Select A or B".
 *   SELECT_N      — At least select_n rows across the option must be satisfied.
 *                   Example: "Complete 1 course from the following".
 */

export function normalizeCourseKey(prefix, number) {
  return `${(prefix || '').trim().toUpperCase()} ${(number || '').trim().toUpperCase()}`
}

export function buildUserCourseMap(courses) {
  const map = new Map()
  for (const course of courses) {
    const key = normalizeCourseKey(course.prefix, course.number)
    if (key.trim()) map.set(key, course)
  }
  return map
}

/**
 * Check whether a single sending CourseGroup is satisfied by the user's courses.
 *
 * Returns:
 *   "satisfied" — requirement fully met
 *   "partial"   — requirement partially met (AND group where some but not all match)
 *   "none"      — no match
 */
export function checkRequirementSatisfied(sendingGroup, userCourseMap) {
  if (!sendingGroup || !sendingGroup.courses || sendingGroup.courses.length === 0) {
    return 'none'
  }
  if (sendingGroup.logic === 'NO_ARTICULATION') {
    return 'none'
  }

  const matches = sendingGroup.courses.filter((c) => {
    const key = normalizeCourseKey(c.prefix, c.number)
    return userCourseMap.has(key)
  })

  if (matches.length === 0) return 'none'

  if (sendingGroup.logic === 'OR' || sendingGroup.logic === 'SINGLE') {
    return 'satisfied'
  }

  // AND logic: need all courses
  if (matches.length === sendingGroup.courses.length) return 'satisfied'
  return 'partial'
}

/**
 * Check whether a single ArticulationRow is satisfied.
 * (Convenience wrapper around checkRequirementSatisfied.)
 */
export function checkRowSatisfied(row, userCourseMap) {
  return checkRequirementSatisfied(row.sending_courses, userCourseMap)
}

/**
 * Determine if a RequirementGroup is satisfied based on its group_logic.
 *
 * COMPLETE_ALL: every row across all options must be satisfied.
 * SELECT_ONE:   any one option where ALL rows are satisfied counts.
 * SELECT_N:     at least select_n rows (across the option's rows) satisfied.
 *
 * Returns "satisfied", "partial", or "none".
 */
export function checkGroupSatisfied(group, userCourseMap) {
  const logic = group.group_logic || 'COMPLETE_ALL'
  const options = group.options || []

  if (options.length === 0) return 'none'

  if (logic === 'SELECT_ONE') {
    // Satisfied if any one complete option is fully met
    let bestPartial = false
    for (const opt of options) {
      const rows = opt.rows || []
      if (rows.length === 0) continue
      const statuses = rows.map((r) => checkRowSatisfied(r, userCourseMap))
      const allSatisfied = statuses.every((s) => s === 'satisfied')
      const anySatisfied = statuses.some((s) => s !== 'none')
      if (allSatisfied) return 'satisfied'
      if (anySatisfied) bestPartial = true
    }
    return bestPartial ? 'partial' : 'none'
  }

  if (logic === 'SELECT_N') {
    const allRows = options.flatMap((o) => o.rows || [])

    // Unit-based selection: "Complete X semester units from the following"
    if (group.select_units) {
      const targetUnits = group.select_units
      let satisfiedUnits = 0
      let anySatisfied = false
      for (const row of allRows) {
        if (checkRowSatisfied(row, userCourseMap) === 'satisfied') {
          anySatisfied = true
          // Sum the receiving (UC) course units for satisfied rows
          const recv = row.receiving_courses
          if (recv?.courses) {
            for (const c of recv.courses) {
              satisfiedUnits += c.units || 0
            }
          }
        }
      }
      if (satisfiedUnits >= targetUnits) return 'satisfied'
      if (anySatisfied) return 'partial'
      return 'none'
    }

    // Course-count selection: "Complete N courses from the following"
    const n = group.select_n || 1
    const satisfiedCount = allRows.filter(
      (r) => checkRowSatisfied(r, userCourseMap) === 'satisfied'
    ).length
    if (satisfiedCount >= n) return 'satisfied'
    if (satisfiedCount > 0) return 'partial'
    return 'none'
  }

  // COMPLETE_ALL (default): every row across all options must be satisfied
  const allRows = options.flatMap((o) => o.rows || [])
  if (allRows.length === 0) return 'none'
  const statuses = allRows.map((r) => checkRowSatisfied(r, userCourseMap))
  if (statuses.every((s) => s === 'satisfied')) return 'satisfied'
  if (statuses.some((s) => s !== 'none')) return 'partial'
  return 'none'
}

/**
 * Compute total and satisfied requirement counts for an agreement.
 *
 * Counting strategy per group_logic:
 *   COMPLETE_ALL — each row is a separate required course, so count rows individually.
 *   SELECT_ONE   — pick one pathway, counts as 1 requirement.
 *   SELECT_N     — pick N courses, counts as N requirements.
 *
 * Handles both formats:
 *   New: sections[].groups[]   — proper group-aware counting
 *   Old: sections[].rows[]     — each row counted as a separate requirement
 *                                 (old behaviour preserved for un-re-scraped files)
 */
export function computeRequirementStats(agreement, userCourseMap) {
  if (!agreement?.sections) return { satisfied: 0, total: 0 }

  let satisfied = 0
  let total = 0

  for (const section of agreement.sections) {
    const groups = section.groups || []

    if (groups.length > 0) {
      // ── New format ────────────────────────────────────────────────────
      for (const group of groups) {
        const options = group.options || []
        const allRows = options.flatMap((o) => o.rows || [])
        if (allRows.length === 0) continue

        const logic = group.group_logic || 'COMPLETE_ALL'

        if (logic === 'SELECT_ONE') {
          // One pathway to choose — counts as 1 requirement
          total++
          if (checkGroupSatisfied(group, userCourseMap) === 'satisfied') satisfied++
        } else if (logic === 'SELECT_N') {
          // Unit-based or course-count pool — counts as 1 requirement
          total++
          if (checkGroupSatisfied(group, userCourseMap) === 'satisfied') satisfied++
        } else {
          // COMPLETE_ALL — each row is a required course
          for (const row of allRows) {
            total++
            if (checkRowSatisfied(row, userCourseMap) === 'satisfied') satisfied++
          }
        }
      }
    } else {
      // ── Old format fallback ───────────────────────────────────────────
      // Each row in the flat list is its own requirement.
      for (const row of section.rows || []) {
        total++
        if (checkRequirementSatisfied(row.sending_courses, userCourseMap) === 'satisfied') {
          satisfied++
        }
      }
    }
  }

  return { satisfied, total }
}

/**
 * Get all CC course keys that the user has matched in this agreement.
 * Used to compute the "Major GPA" from only matched courses.
 */
export function getMatchedCourseKeys(agreement, userCourseMap) {
  const matched = new Set()
  if (!agreement?.sections) return matched

  for (const section of agreement.sections) {
    const groups = section.groups || []

    if (groups.length > 0) {
      // New format
      for (const group of groups) {
        for (const option of group.options || []) {
          for (const row of option.rows || []) {
            _collectMatchedFromRow(row, userCourseMap, matched)
          }
        }
      }
    } else {
      // Old format
      for (const row of section.rows || []) {
        _collectMatchedFromRow(row, userCourseMap, matched)
      }
    }
  }
  return matched
}

function _collectMatchedFromRow(row, userCourseMap, matched) {
  const sending = row.sending_courses
  if (!sending?.courses) return
  for (const course of sending.courses) {
    const key = normalizeCourseKey(course.prefix, course.number)
    if (userCourseMap.has(key)) {
      matched.add(key)
    }
  }
}

// ---------------------------------------------------------------------------
// DEPRECATED — kept only for old-format data compatibility
// ---------------------------------------------------------------------------

/**
 * @deprecated Use group-aware computeRequirementStats() instead.
 *
 * parsePathwayGroups() was a workaround that tried to extract "Select A or B"
 * grouping by parsing the plain-text notes field. It was fragile and incomplete.
 * New scraped data has proper group structure in sections[].groups[], making
 * this function unnecessary.
 *
 * It is kept here because:
 *   1. Old-format JSON files (not yet re-scraped) still have flat rows[].
 *   2. The old computeRequirementStats() called it.
 *   3. TransferRequirements.jsx still imports it for old-format fallback.
 * Once all data is re-scraped, this can be removed.
 */
export function parsePathwayGroups(notes) {
  if (!notes?.length) return []
  const fullText = notes.join(' ')

  const idx = fullText.toLowerCase().indexOf('choose one of the following')
  if (idx === -1) return []

  const after = fullText.substring(idx)
  const endPatterns = [/Upper.division/i, /All majors/i, /required to undertake/i]
  let blockEnd = after.length
  for (const p of endPatterns) {
    const m = after.search(p)
    if (m > 0 && m < blockEnd) blockEnd = m
  }
  const block = after.substring(0, blockEnd)

  const segments = block.split(':')
  const allKeys = new Set()
  const pathways = []

  for (let i = 1; i < segments.length; i++) {
    const seg = segments[i]
    const orParts = seg.includes(') or (') ? seg.split(/\)\s*or\s*\(/) : [seg]
    for (const part of orParts) {
      const keys = extractCourseKeysFromText(part)
      if (keys.length > 0) {
        pathways.push(keys)
        keys.forEach((k) => allKeys.add(k))
      }
    }
  }

  if (allKeys.size === 0 || pathways.length === 0) return []
  return [{ receivingKeys: allKeys, pathways }]
}

function extractCourseKeysFromText(text) {
  const keys = []
  const re = /\b([A-Z]{2,6})\s+(\d{1,4}[A-Z]?(?:-[A-Z])?)\b/g
  let m
  while ((m = re.exec(text)) !== null) {
    const prefix = m[1]
    const number = m[2]
    const rangeMatch = number.match(/^(\d+)([A-Z])-([A-Z])$/)
    if (rangeMatch) {
      const base = rangeMatch[1]
      const start = rangeMatch[2].charCodeAt(0)
      const end = rangeMatch[3].charCodeAt(0)
      for (let c = start; c <= end; c++) {
        keys.push(`${prefix} ${base}${String.fromCharCode(c)}`)
      }
    } else {
      keys.push(`${prefix} ${number}`)
    }
  }
  return keys
}
