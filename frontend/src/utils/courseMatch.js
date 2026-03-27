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
