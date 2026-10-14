const IQR_TO_SD = 1.349

function normalCdf(z) {
  const t = 1 / (1 + 0.2316419 * Math.abs(z))
  const poly = t * (0.31938153 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
  const tail = Math.exp(-0.5 * z * z) / Math.sqrt(2 * Math.PI) * poly
  return z >= 0 ? 1 - tail : tail
}

export function gpaPercentile(gpa, q1, q3) {
  if (gpa == null || q1 == null || q3 == null || q3 < q1) return null
  const sd = (q3 - q1) / IQR_TO_SD
  if (sd === 0) return gpa >= q1 ? 100 : 0
  const z = (gpa - (q1 + q3) / 2) / sd
  return Math.round(normalCdf(z) * 100)
}

export function admitTier(percentile, admitRate) {
  if (percentile == null) return null
  const rate = admitRate ?? 0
  if (percentile < 25 || (rate < 15 && percentile < 60)) return 'reach'
  if ((rate >= 30 && percentile >= 60) || (rate >= 60 && percentile >= 40)) return 'likely'
  return 'match'
}

export function gpaNeeded(currentGPA, gradedUnits, remainingUnits, targetGPA) {
  if (targetGPA == null || !(remainingUnits > 0)) return null
  const done = gradedUnits > 0 ? gradedUnits : 0
  const current = currentGPA ?? 0
  return (targetGPA * (done + remainingUnits) - current * done) / remainingUnits
}

export function ordinal(n) {
  const mod100 = n % 100
  if (mod100 >= 11 && mod100 <= 13) return `${n}th`
  const suffix = { 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] || 'th'
  return `${n}${suffix}`
}
