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

// Returns "satisfied", "partial", or "none" based on logic type:
// SINGLE/OR: any match → satisfied. AND: all → satisfied, some → partial.
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

  if (matches.length === sendingGroup.courses.length) return 'satisfied'
  return 'partial'
}

// Parse notes to find "choose one of the following" pathway groups.
// Returns array of { receivingKeys: Set<string>, pathways: string[][] }
// Each pathway is an array of UC receiving course keys forming one option.
export function parsePathwayGroups(notes) {
  if (!notes?.length) return []
  const fullText = notes.join(' ')

  const idx = fullText.toLowerCase().indexOf('choose one of the following')
  if (idx === -1) return []

  const after = fullText.substring(idx)

  // Find block boundary (next major section)
  const endPatterns = [/Upper.division/i, /All majors/i, /required to undertake/i]
  let blockEnd = after.length
  for (const p of endPatterns) {
    const m = after.search(p)
    if (m > 0 && m < blockEnd) blockEnd = m
  }
  const block = after.substring(0, blockEnd)

  // Split by ":" to find pathway categories
  const segments = block.split(':')
  const allKeys = new Set()
  const pathways = []

  for (let i = 1; i < segments.length; i++) {
    const seg = segments[i]

    // Split by ") or (" for sub-options within a category
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

    // Handle range: "14A-B" → 14A, 14B
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

// Compute requirement stats with pathway group awareness.
// "Choose one" pathway groups count as 1 requirement, satisfied if any
// complete pathway within the group has all its CC equivalents met.
export function computeRequirementStats(agreement, userCourseMap) {
  if (!agreement?.sections) return { satisfied: 0, total: 0 }

  const pathwayGroups = parsePathwayGroups(agreement.notes)

  // Set of UC receiving course keys that belong to a pathway group
  const groupedKeys = new Set()
  for (const group of pathwayGroups) {
    for (const key of group.receivingKeys) {
      groupedKeys.add(key)
    }
  }

  // Collect all rows and build receiving key → row lookup
  const allRows = []
  for (const section of agreement.sections) {
    for (const row of section.rows || []) {
      allRows.push(row)
    }
  }

  const rowByReceivingKey = new Map()
  for (const row of allRows) {
    if (!row.receiving_courses?.courses) continue
    for (const c of row.receiving_courses.courses) {
      const key = normalizeCourseKey(c.prefix, c.number)
      rowByReceivingKey.set(key, row)
    }
  }

  let satisfied = 0
  let total = 0
  const processedGroups = new Set()

  for (const row of allRows) {
    const receivingKey = row.receiving_courses?.courses?.[0]
      ? normalizeCourseKey(row.receiving_courses.courses[0].prefix, row.receiving_courses.courses[0].number)
      : null

    if (receivingKey && groupedKeys.has(receivingKey)) {
      // Find which pathway group this row belongs to
      const group = pathwayGroups.find((g) => g.receivingKeys.has(receivingKey))
      if (group && !processedGroups.has(group)) {
        processedGroups.add(group)
        total++

        // Check if any pathway option is fully satisfied
        let groupSatisfied = false
        for (const pathway of group.pathways) {
          let allMet = true
          for (const courseKey of pathway) {
            const pRow = rowByReceivingKey.get(courseKey)
            if (!pRow) { allMet = false; break }
            if (checkRequirementSatisfied(pRow.sending_courses, userCourseMap) !== 'satisfied') {
              allMet = false; break
            }
          }
          if (allMet) { groupSatisfied = true; break }
        }

        if (groupSatisfied) satisfied++
      }
      continue // skip individual counting for grouped rows
    }

    // Regular individual requirement
    total++
    if (checkRequirementSatisfied(row.sending_courses, userCourseMap) === 'satisfied') {
      satisfied++
    }
  }

  return { satisfied, total }
}

export function getMatchedCourseKeys(agreement, userCourseMap) {
  const matched = new Set()
  if (!agreement?.sections) return matched

  for (const section of agreement.sections) {
    for (const row of section.rows || []) {
      const sending = row.sending_courses
      if (!sending?.courses) continue
      for (const course of sending.courses) {
        const key = normalizeCourseKey(course.prefix, course.number)
        if (userCourseMap.has(key)) {
          matched.add(key)
        }
      }
    }
  }
  return matched
}
