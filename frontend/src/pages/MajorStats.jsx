import { useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Title, SimpleGrid, Table, Loader, Alert, Text } from '@mantine/core'
import { useMajorStats, useMajors } from '../hooks/useApi'
import StatsCard from '../components/StatsCard'
import TrendChart from '../components/TrendChart'
import FilterBar from '../components/FilterBar'

export default function MajorStats() {
  const { major } = useParams()
  const navigate = useNavigate()
  const { data: majors } = useMajors()
  const decodedMajor = major ? decodeURIComponent(major) : null
  const { data: stats, loading, error } = useMajorStats(decodedMajor)

  // Unique universities in the result
  const universities = useMemo(() => {
    if (!stats) return []
    return [...new Set(stats.map((s) => s.university))].sort()
  }, [stats])

  // Pivot for chart: one row per year, one column per university
  const chartData = useMemo(() => {
    if (!stats) return []
    const byYear = {}
    stats.forEach((row) => {
      if (!byYear[row.year]) byYear[row.year] = { year: row.year }
      byYear[row.year][row.university] = row.avg_admit_rate != null
        ? Math.round(row.avg_admit_rate * 10) / 10
        : null
    })
    return Object.values(byYear).sort((a, b) => a.year - b.year)
  }, [stats])

  const chartSeries = universities.map((u) => ({ key: u, label: u }))

  // Per-university aggregates
  const uniTotals = useMemo(() => {
    if (!stats) return []
    const totals = {}
    stats.forEach((row) => {
      if (!totals[row.university]) {
        totals[row.university] = {
          applicants: 0, admits: 0, enrolls: 0,
          rateSum: 0, count: 0, gpaMinSum: 0, gpaMaxSum: 0, gpaCount: 0,
        }
      }
      const t = totals[row.university]
      t.applicants += row.total_applicants || 0
      t.admits += row.total_admits || 0
      t.enrolls += row.total_enrolls || 0
      if (row.avg_admit_rate != null) { t.rateSum += row.avg_admit_rate; t.count++ }
      if (row.avg_admit_gpa_min != null) { t.gpaMinSum += parseFloat(row.avg_admit_gpa_min); t.gpaCount++ }
      if (row.avg_admit_gpa_max != null) { t.gpaMaxSum += parseFloat(row.avg_admit_gpa_max) }
    })
    return Object.entries(totals).map(([uni, t]) => ({
      university: uni,
      applicants: t.applicants,
      admits: t.admits,
      enrolls: t.enrolls,
      avgRate: t.count > 0 ? (t.rateSum / t.count).toFixed(1) : 'N/A',
      gpaRange: t.gpaCount > 0
        ? `${(t.gpaMinSum / t.gpaCount).toFixed(2)} - ${(t.gpaMaxSum / t.gpaCount).toFixed(2)}`
        : 'N/A',
    })).sort((a, b) => a.university.localeCompare(b.university))
  }, [stats])

  const validUnis = uniTotals.filter((u) => u.avgRate !== 'N/A')
  const mostCompetitive = validUnis.length
    ? validUnis.reduce((a, b) => (parseFloat(a.avgRate) < parseFloat(b.avgRate) ? a : b))
    : null
  const leastCompetitive = validUnis.length
    ? validUnis.reduce((a, b) => (parseFloat(a.avgRate) > parseFloat(b.avgRate) ? a : b))
    : null

  const majorOptions = (majors || []).map((m) => ({ value: m, label: m }))

  return (
    <>
      <Title order={2} mb="md">Major Stats{decodedMajor ? `: ${decodedMajor}` : ''}</Title>

      <FilterBar
        filters={[
          {
            type: 'select',
            label: 'Select Major',
            value: decodedMajor || null,
            onChange: (val) => navigate(val ? `/major/${encodeURIComponent(val)}` : '/major'),
            data: majorOptions,
            placeholder: 'Search for a major',
            searchable: true,
          },
        ]}
      />

      {!decodedMajor && <Text c="dimmed">Search and select a major above to view statistics.</Text>}
      {loading && <Loader m="xl" />}
      {error && <Alert color="red" title="Error">{error}</Alert>}

      {stats && (
        <>
          <TrendChart
            data={chartData}
            xKey="year"
            series={chartSeries}
            yLabel="Avg Admit Rate (%)"
          />

          <SimpleGrid cols={{ base: 1, sm: 2, md: 4 }} mt="lg" mb="lg">
            <StatsCard title="UCs Offering This Major" value={universities.length} />
            {mostCompetitive && (
              <StatsCard
                title="Most Competitive"
                value={mostCompetitive.university}
                subtitle={`${mostCompetitive.avgRate}% avg admit rate`}
              />
            )}
            {leastCompetitive && (
              <StatsCard
                title="Least Competitive"
                value={leastCompetitive.university}
                subtitle={`${leastCompetitive.avgRate}% avg admit rate`}
              />
            )}
            <StatsCard
              title="Total Applicants"
              value={uniTotals.reduce((s, u) => s + u.applicants, 0).toLocaleString()}
            />
          </SimpleGrid>

          <Title order={4} mb="sm">By University</Title>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>University</Table.Th>
                <Table.Th>Applicants</Table.Th>
                <Table.Th>Admits</Table.Th>
                <Table.Th>Avg Admit Rate</Table.Th>
                <Table.Th>GPA Range</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {uniTotals.map((row) => (
                <Table.Tr key={row.university}>
                  <Table.Td>{row.university}</Table.Td>
                  <Table.Td>{row.applicants.toLocaleString()}</Table.Td>
                  <Table.Td>{row.admits.toLocaleString()}</Table.Td>
                  <Table.Td>{row.avgRate}%</Table.Td>
                  <Table.Td>{row.gpaRange}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </>
      )}
    </>
  )
}
