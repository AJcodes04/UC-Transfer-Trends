export const GRADE_OPTIONS = [
  'A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-',
  'D+', 'D', 'D-', 'F', 'P', 'NP',
  { value: 'IP', label: 'In progress' },
]

export const NON_TRANSFERABLE = new Set(['F', 'NP', 'W', 'I', 'IP', 'NC'])
export const NOT_COMPLETED = new Set(['IP', 'W', 'I'])

export function transferableUnits(courses) {
  let total = 0
  for (const c of courses) {
    if (!NON_TRANSFERABLE.has((c.grade || '').trim().toUpperCase())) total += parseFloat(c.units) || 0
  }
  return total
}
