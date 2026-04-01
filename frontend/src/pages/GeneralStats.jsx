import { useState, useMemo, useEffect } from 'react'
import { Title, SimpleGrid, Table, Loader, Alert, Slider, Text, Group } from '@mantine/core'
import { useGeneralStats } from '../hooks/useApi'
import StatsCard from '../components/StatsCard'
import TrendChart from '../components/TrendChart'
import { UC_COLORS } from '../utils/ucColors'

const Y_AXIS_OPTIONS = [
  { value: 'admitRate', label: 'Admit Rate (%)' },
  { value: 'gpa', label: 'Lowest GPA (25th percentile)' },
]

export default function GeneralStats() {
  const { data: stats, loading, error } = useGeneralStats()
  const [yAxis, setYAxis] = useState('admitRate')
  const [selectedYear, setSelectedYear] = useState(null)

  const allUCs = useMemo(() => {
    if (!stats) return []
    return [...new Set(stats.map((s) => s.campus))].sort()
  }, [stats])

  const chartData = useMemo(() => {
    if (!stats) return []
    const byYear = {}
    stats.forEach((row) => {
      if (!byYear[row.year]) byYear[row.year] = { year: row.year }
      if (yAxis === 'gpa') {
        if (row.admit_gpa_min != null) {
          byYear[row.year][row.campus] = parseFloat(row.admit_gpa_min)
        }
      } else {
        byYear[row.year][row.campus] = row.admit_rate
      }
    })
    return Object.values(byYear).sort((a, b) => a.year - b.year)
  }, [stats, yAxis])

  const chartSeries = allUCs.map((uc) => ({ key: uc, label: uc }))

  const availableYears = useMemo(() => {
    if (!stats) return []
    return [...new Set(stats.map((s) => s.year))].sort((a, b) => a - b)
  }, [stats])

  useEffect(() => {
    if (availableYears.length && selectedYear === null) {
      setSelectedYear(availableYears[availableYears.length - 1])
    }
  }, [availableYears])

  const yearMarks = useMemo(() => {
    return availableYears.map((y) => ({ value: y, label: String(y) }))
  }, [availableYears])

  const schoolTotals = useMemo(() => {
    if (!stats) return []
    const filtered = selectedYear ? stats.filter((row) => row.year === selectedYear) : stats
    const totals = {}
    filtered.forEach((row) => {
      if (!totals[row.campus]) {
        totals[row.campus] = { applicants: 0, admits: 0, enrolls: 0, count: 0, rateSum: 0 }
      }
      const t = totals[row.campus]
      t.applicants += row.applicants || 0
      t.admits += row.admits || 0
      t.enrolls += row.enrolls || 0
      if (row.admit_rate != null) {
        t.rateSum += row.admit_rate
        t.count += 1
      }
    })
    return Object.entries(totals).map(([campus, t]) => ({
      campus,
      applicants: t.applicants,
      admits: t.admits,
      enrolls: t.enrolls,
      avgRate: t.count > 0 ? (t.rateSum / t.count).toFixed(1) : 'N/A',
    })).sort((a, b) => a.campus.localeCompare(b.campus))
  }, [stats, selectedYear])

  const cardYear = selectedYear || (availableYears.length ? availableYears[availableYears.length - 1] : null)
  const prevCardYear = cardYear ? cardYear - 1 : null

  const overallAvg = useMemo(() => {
    if (!stats || !cardYear) return { current: 'N/A', prev: 'N/A' }
    const forYear = (y) => {
      const rows = stats.filter((r) => r.year === y && r.admit_rate != null)
      if (!rows.length) return null
      return (rows.reduce((sum, r) => sum + r.admit_rate, 0) / rows.length).toFixed(1)
    }
    return { current: forYear(cardYear), prev: forYear(prevCardYear) }
  }, [stats, cardYear, prevCardYear])

  const mostCompetitive = useMemo(() => {
    if (!stats || !cardYear) return { current: null, prev: null }
    const forYear = (y) => {
      const rows = stats.filter((r) => r.year === y && r.admit_rate != null)
      if (!rows.length) return null
      return rows.reduce((best, r) => (!best || r.admit_rate < best.admit_rate ? r : best), null)
    }
    return { current: forYear(cardYear), prev: forYear(prevCardYear) }
  }, [stats, cardYear, prevCardYear])

  const avgGpaRange = useMemo(() => {
    if (!stats || !cardYear) return null
    const rows = stats.filter((r) => r.year === cardYear)
    const mins = rows.filter((r) => r.admit_gpa_min != null).map((r) => parseFloat(r.admit_gpa_min))
    const maxes = rows.filter((r) => r.admit_gpa_max != null).map((r) => parseFloat(r.admit_gpa_max))
    if (!mins.length || !maxes.length) return null
    const avgMin = (mins.reduce((a, b) => a + b, 0) / mins.length).toFixed(2)
    const avgMax = (maxes.reduce((a, b) => a + b, 0) / maxes.length).toFixed(2)
    return { min: avgMin, max: avgMax }
  }, [stats, cardYear])

  const enrollTotals = useMemo(() => {
    if (!stats || !cardYear) return { current: null, prev: null }
    const forYear = (y) => {
      const rows = stats.filter((r) => r.year === y)
      if (!rows.length) return null
      return rows.reduce((sum, r) => sum + (r.enrolls || 0), 0)
    }
    return { current: forYear(cardYear), prev: forYear(prevCardYear) }
  }, [stats, cardYear, prevCardYear])

  function yoyChange(latest, prev) {
    if (!latest || !prev || prev === 0) return null
    return ((latest - prev) / prev * 100).toFixed(1)
  }

  if (loading) return <Loader m="xl" />
  if (error) return <Alert color="red" title="Error">{error}</Alert>

  return (
    <>
      <Title order={2} mb="md">General UC Admission Rates</Title>

      <TrendChart
        data={chartData}
        xKey="year"
        series={chartSeries}
        colorMap={UC_COLORS}
        yLabel={yAxis === 'gpa' ? 'Lowest GPA (25th percentile)' : 'Admit Rate (%)'}
        yAxisOptions={Y_AXIS_OPTIONS}
        onYAxisChange={setYAxis}
        yDomain={yAxis === 'gpa' ? [2.4, 4.0] : undefined}
        tooltipSuffix={yAxis === 'gpa' ? '' : '%'}
      />

      <SimpleGrid cols={{ base: 1, sm: 2, md: 4 }} mt="lg" mb="lg">
        <StatsCard
          title={`Avg Admit Rate (${cardYear || ''})`}
          value={overallAvg.current ? `${overallAvg.current}%` : 'N/A'}
          change={yoyChange(parseFloat(overallAvg.current), parseFloat(overallAvg.prev))}
          subtitle={overallAvg.prev ? `vs ${overallAvg.prev}% in ${prevCardYear}` : undefined}
        />
        <StatsCard
          title={`Most Competitive (${cardYear || ''})`}
          value={mostCompetitive.current ? `${mostCompetitive.current.campus}` : '-'}
          change={mostCompetitive.current && mostCompetitive.prev
            ? yoyChange(mostCompetitive.current.admit_rate, mostCompetitive.prev.admit_rate)
            : null}
          subtitle={mostCompetitive.current
            ? `${mostCompetitive.current.admit_rate}% admit rate${mostCompetitive.prev ? ` vs ${mostCompetitive.prev.admit_rate}% in ${prevCardYear}` : ''}`
            : undefined}
        />
        <StatsCard
          title={`Avg GPA Range (${cardYear || ''})`}
          value={avgGpaRange ? `${avgGpaRange.min} – ${avgGpaRange.max}` : 'N/A'}
        />
        <StatsCard
          title={`Enrolls (${cardYear || ''})`}
          value={enrollTotals.current != null ? enrollTotals.current.toLocaleString() : '-'}
          change={yoyChange(enrollTotals.current, enrollTotals.prev)}
          subtitle={enrollTotals.prev != null ? `vs ${enrollTotals.prev.toLocaleString()} in ${prevCardYear}` : undefined}
        />
      </SimpleGrid>

      <Group justify="space-between" align="center" mb="sm">
        <Title order={4}>By University</Title>
        <Text size="sm" c="dimmed">{selectedYear || 'All Years'}</Text>
      </Group>
      {availableYears.length > 1 && (
        <Slider
          value={selectedYear || availableYears[0]}
          onChange={setSelectedYear}
          min={availableYears[0]}
          max={availableYears[availableYears.length - 1]}
          step={1}
          marks={yearMarks}
          mb="xl"
          styles={{ markLabel: { fontSize: 10 } }}
        />
      )}
      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>University</Table.Th>
            <Table.Th>Applicants</Table.Th>
            <Table.Th>Admits</Table.Th>
            <Table.Th>Enrolls</Table.Th>
            <Table.Th>Admit Rate</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {schoolTotals.map((row) => (
            <Table.Tr key={row.campus}>
              <Table.Td>{row.campus}</Table.Td>
              <Table.Td>{row.applicants.toLocaleString()}</Table.Td>
              <Table.Td>{row.admits.toLocaleString()}</Table.Td>
              <Table.Td>{row.enrolls.toLocaleString()}</Table.Td>
              <Table.Td>{row.avgRate}%</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </>
  )
}
