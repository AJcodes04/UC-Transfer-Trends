import { calculateGPA } from './gpa'
import { transferableUnits } from './grades'
export const SEASONS = ['Winter', 'Spring', 'Summer', 'Fall']

export const SEASON_COLORS = { Winter: 'blue', Spring: 'yellow', Summer: 'orange', Fall: 'red' }

export function parseTerm(term) {
  const m = /^(winter|spring|summer|fall)\s+(\d{4})$/i.exec((term || '').trim())
  if (!m) return null
  const season = m[1][0].toUpperCase() + m[1].slice(1).toLowerCase()
  return { season, year: parseInt(m[2], 10) }
}

export function formatTerm(season, year) {
  return season && year ? `${season} ${year}` : ''
}

function sortKey(term) {
  const parsed = parseTerm(term)
  return parsed ? parsed.year * 10 + SEASONS.indexOf(parsed.season) : -1
}

export function groupByTerm(courses) {
  const groups = new Map()
  for (const course of courses) {
    const parsed = parseTerm(course.term)
    const key = parsed ? formatTerm(parsed.season, parsed.year) : ''
    if (!groups.has(key)) groups.set(key, { term: key, season: parsed?.season || null, courses: [] })
    groups.get(key).courses.push(course)
  }
  return [...groups.values()].sort((a, b) => {
    const ka = sortKey(a.term), kb = sortKey(b.term)
    if (ka < 0 || kb < 0) return kb - ka
    return ka - kb
  })
}

export function toEditForm(course) {
  const parsed = parseTerm(course.term)
  return {
    prefix: course.prefix || '',
    number: course.number || '',
    title: course.title || '',
    units: course.units,
    grade: course.grade || null,
    season: parsed?.season || null,
    year: parsed?.year || '',
  }
}

export function fromEditForm(form) {
  return {
    prefix: form.prefix.trim().toUpperCase(),
    number: form.number.trim(),
    title: form.title.trim(),
    units: form.units,
    grade: form.grade,
    term: formatTerm(form.season, form.year),
  }
}

export function termTrend(courses) {
  const seen = []
  return groupByTerm(courses)
    .filter((g) => g.season)
    .map((g) => {
      seen.push(...g.courses)
      return {
        term: g.term,
        season: g.season,
        termGPA: calculateGPA(g.courses),
        cumulativeGPA: calculateGPA(seen),
        termUnits: transferableUnits(g.courses),
        cumulativeUnits: transferableUnits(seen),
      }
    })
}
