const GRADE_POINTS = {
  'A+': 4.0, 'A': 4.0, 'A-': 3.7,
  'B+': 3.3, 'B': 3.0, 'B-': 2.7,
  'C+': 2.3, 'C': 2.0, 'C-': 1.7,
  'D+': 1.3, 'D': 1.0, 'D-': 0.7,
  'F': 0.0,
}

const EXCLUDED_GRADES = new Set(['P', 'NP', 'W', 'I', 'IP', 'CR', 'NC'])

export function calculateGPA(courses) {
  let totalPoints = 0
  let totalUnits = 0

  for (const course of courses) {
    const grade = (course.grade || '').trim().toUpperCase()
    if (EXCLUDED_GRADES.has(grade) || !(grade in GRADE_POINTS)) continue
    const units = parseFloat(course.units) || 0
    if (units <= 0) continue
    totalPoints += GRADE_POINTS[grade] * units
    totalUnits += units
  }

  if (totalUnits === 0) return null
  return Math.round((totalPoints / totalUnits) * 100) / 100
}

export { GRADE_POINTS, EXCLUDED_GRADES }
