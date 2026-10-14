const TREND_THRESHOLD_PTS = 2

function sum(rows, key) {
  return rows.reduce((s, r) => s + (r[key] || 0), 0)
}

function ratio(rows, num, den, scale = 1) {
  const d = sum(rows, den)
  return d > 0 ? (sum(rows, num) / d) * scale : null
}

function gpaFloor(rows) {
  const valid = rows.filter((r) => r.gpaMin != null && r.admits > 0)
  const weight = sum(valid, 'admits')
  return weight > 0 ? valid.reduce((s, r) => s + r.gpaMin * r.admits, 0) / weight : null
}

const METRICS = {
  admitRate: (rows) => ratio(rows, 'admits', 'applicants', 100),
  perSeat: (rows) => ratio(rows, 'applicants', 'enrolls'),
  gpaFloor,
}

function delta(current, previous) {
  return current != null && previous != null ? current - previous : null
}

export function computeCardStats(rows, year, lookback = 3) {
  if (!rows.length || !year) return null
  const byYear = {}
  for (const r of rows) (byYear[r.year] ||= []).push(r)
  const years = Array.from({ length: lookback + 1 }, (_, i) => year - lookback + i)

  const metric = (key) => {
    const at = (y) => (byYear[y] ? METRICS[key](byYear[y]) : null)
    const value = at(year)
    return {
      value,
      delta: delta(value, at(year - 1)),
      lookbackDelta: delta(value, at(year - lookback)),
      series: years.map((y) => ({ year: y, value: at(y) })),
    }
  }

  const admitRate = metric('admitRate')
  const direction = admitRate.lookbackDelta == null ? null
    : admitRate.lookbackDelta <= -TREND_THRESHOLD_PTS ? 'More selective'
    : admitRate.lookbackDelta >= TREND_THRESHOLD_PTS ? 'Less selective'
    : 'Steady'

  return { admitRate, gpaFloor: metric('gpaFloor'), perSeat: metric('perSeat'), direction, lookback }
}

export function formatDelta(value, digits = 1, unit = '') {
  if (value == null) return null
  return `${value.toFixed(digits)}${unit}`
}
