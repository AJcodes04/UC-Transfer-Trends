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

  const overallAvg = useMemo(() => {
    if (!schoolTotals.length) return 'N/A'
    const valid = schoolTotals.filter((s) => s.avgRate !== 'N/A')
    if (!valid.length) return 'N/A'
    const avg = valid.reduce((sum, s) => sum + parseFloat(s.avgRate), 0) / valid.length
    return avg.toFixed(1) + '%'
  }, [schoolTotals])

  const yearlyTotals = useMemo(() => {
    if (!stats) return { latest: null, prev: null }
    const byYear = {}
    stats.forEach((row) => {
      if (!byYear[row.year]) byYear[row.year] = { applicants: 0, admits: 0, enrolls: 0 }
      byYear[row.year].applicants += row.applicants || 0
      byYear[row.year].admits += row.admits || 0
      byYear[row.year].enrolls += row.enrolls || 0
    })
    const years = Object.keys(byYear).map(Number).sort((a, b) => b - a)
    return {
      latest: years[0] ? { year: years[0], ...byYear[years[0]] } : null,
      prev: years[1] ? { year: years[1], ...byYear[years[1]] } : null,
    }
  }, [stats])

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
        <StatsCard title="Overall Avg Admit Rate" value={overallAvg} />
        <StatsCard
          title={`Applicants (${yearlyTotals.latest?.year || ''})`}
          value={yearlyTotals.latest?.applicants.toLocaleString() || '-'}
          change={yoyChange(yearlyTotals.latest?.applicants, yearlyTotals.prev?.applicants)}
          subtitle={yearlyTotals.prev ? `vs ${yearlyTotals.prev.applicants.toLocaleString()} in ${yearlyTotals.prev.year}` : undefined}
        />
        <StatsCard
          title={`Admits (${yearlyTotals.latest?.year || ''})`}
          value={yearlyTotals.latest?.admits.toLocaleString() || '-'}
          change={yoyChange(yearlyTotals.latest?.admits, yearlyTotals.prev?.admits)}
          subtitle={yearlyTotals.prev ? `vs ${yearlyTotals.prev.admits.toLocaleString()} in ${yearlyTotals.prev.year}` : undefined}
        />
        <StatsCard
          title={`Enrolls (${yearlyTotals.latest?.year || ''})`}
          value={yearlyTotals.latest?.enrolls.toLocaleString() || '-'}
          change={yoyChange(yearlyTotals.latest?.enrolls, yearlyTotals.prev?.enrolls)}
          subtitle={yearlyTotals.prev ? `vs ${yearlyTotals.prev.enrolls.toLocaleString()} in ${yearlyTotals.prev.year}` : undefined}
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
