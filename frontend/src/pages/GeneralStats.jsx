import { useState, useMemo } from 'react'
import { Title, SimpleGrid, Table, Loader, Alert, Text } from '@mantine/core'
import { useGeneralStats, useUniversities } from '../hooks/useApi'
import StatsCard from '../components/StatsCard'
import TrendChart from '../components/TrendChart'
import FilterBar from '../components/FilterBar'

export default function GeneralStats() {
  const { data: stats, loading, error } = useGeneralStats()
  const { data: universities } = useUniversities()
  const [selectedUCs, setSelectedUCs] = useState([])

  // Get the list of unique UCs from the stats data
  const allUCs = useMemo(() => {
    if (!stats) return []
    return [...new Set(stats.map((s) => s.university))].sort()
  }, [stats])

  // Which UCs to display — if none selected, show all
  const activeUCs = selectedUCs.length > 0 ? selectedUCs : allUCs

  // Pivot data for the chart: one row per year, one column per UC
  const chartData = useMemo(() => {
    if (!stats) return []

    const byYear = {}
    stats.forEach((row) => {
      if (!activeUCs.includes(row.university)) return
      if (!byYear[row.year]) byYear[row.year] = { year: row.year }
      byYear[row.year][row.university] = row.avg_admit_rate != null
        ? Math.round(row.avg_admit_rate * 10) / 10
        : null
    })

    return Object.values(byYear).sort((a, b) => a.year - b.year)
  }, [stats, activeUCs])

  // Series definitions for the chart (one line per UC)
  const chartSeries = activeUCs.map((uc) => ({ key: uc, label: uc }))

  // Aggregate per-school totals for the stat cards
  const schoolTotals = useMemo(() => {
    if (!stats) return []
    const totals = {}
    stats.forEach((row) => {
      if (!totals[row.university]) {
        totals[row.university] = { applicants: 0, admits: 0, enrolls: 0, count: 0, rateSum: 0 }
      }
      const t = totals[row.university]
      t.applicants += row.total_applicants || 0
      t.admits += row.total_admits || 0
      t.enrolls += row.total_enrolls || 0
      if (row.avg_admit_rate != null) {
        t.rateSum += row.avg_admit_rate
        t.count += 1
      }
    })
    return Object.entries(totals).map(([uni, t]) => ({
      university: uni,
      applicants: t.applicants,
      admits: t.admits,
      enrolls: t.enrolls,
      avgRate: t.count > 0 ? (t.rateSum / t.count).toFixed(1) : 'N/A',
    })).sort((a, b) => a.university.localeCompare(b.university))
  }, [stats])

  // Overall average admit rate
  const overallAvg = useMemo(() => {
    if (!schoolTotals.length) return 'N/A'
    const valid = schoolTotals.filter((s) => s.avgRate !== 'N/A')
    if (!valid.length) return 'N/A'
    const avg = valid.reduce((sum, s) => sum + parseFloat(s.avgRate), 0) / valid.length
    return avg.toFixed(1) + '%'
  }, [schoolTotals])

  if (loading) return <Loader m="xl" />
  if (error) return <Alert color="red" title="Error">{error}</Alert>

  return (
    <>
      <Title order={2} mb="md">General UC Admission Rates</Title>

      <FilterBar
        filters={[
          {
            type: 'multiselect',
            label: 'Filter UCs',
            value: selectedUCs,
            onChange: setSelectedUCs,
            data: allUCs,
            placeholder: 'All UCs shown',
          },
        ]}
      />

      <TrendChart
        data={chartData}
        xKey="year"
        series={chartSeries}
        yLabel="Avg Admit Rate (%)"
      />

      <SimpleGrid cols={{ base: 1, sm: 2, md: 4 }} mt="lg" mb="lg">
        <StatsCard title="Overall Avg Admit Rate" value={overallAvg} />
        <StatsCard
          title="Total Applicants"
          value={schoolTotals.reduce((s, t) => s + t.applicants, 0).toLocaleString()}
        />
        <StatsCard
          title="Total Admits"
          value={schoolTotals.reduce((s, t) => s + t.admits, 0).toLocaleString()}
        />
        <StatsCard
          title="Total Enrolls"
          value={schoolTotals.reduce((s, t) => s + t.enrolls, 0).toLocaleString()}
        />
      </SimpleGrid>

      <Title order={4} mb="sm">By University</Title>
      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>University</Table.Th>
            <Table.Th>Applicants</Table.Th>
            <Table.Th>Admits</Table.Th>
            <Table.Th>Enrolls</Table.Th>
            <Table.Th>Avg Admit Rate</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {schoolTotals.map((row) => (
            <Table.Tr key={row.university}>
              <Table.Td>{row.university}</Table.Td>
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
