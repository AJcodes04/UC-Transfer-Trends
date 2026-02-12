import { useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Title, SimpleGrid, Table, Loader, Alert, Text } from '@mantine/core'
import { useSchoolStats, useUniversities } from '../hooks/useApi'
import StatsCard from '../components/StatsCard'
import TrendChart from '../components/TrendChart'
import FilterBar from '../components/FilterBar'

export default function SchoolStats() {
  const { school } = useParams()
  const navigate = useNavigate()
  const { data: universities } = useUniversities()
  const { data: stats, loading, error } = useSchoolStats(school)

  // Get unique colleges within this school for the chart
  const colleges = useMemo(() => {
    if (!stats) return []
    return [...new Set(stats.map((s) => s.college_school))].sort()
  }, [stats])

  // Pivot for chart: one row per year, one column per college
  const chartData = useMemo(() => {
    if (!stats) return []
    const byYear = {}
    stats.forEach((row) => {
      if (!byYear[row.year]) byYear[row.year] = { year: row.year }
      byYear[row.year][row.college_school] = row.avg_admit_rate != null
        ? Math.round(row.avg_admit_rate * 10) / 10
        : null
    })
    return Object.values(byYear).sort((a, b) => a.year - b.year)
  }, [stats])

  const chartSeries = colleges.map((c) => ({ key: c, label: c }))

  // Per-college aggregate stats
  const collegeTotals = useMemo(() => {
    if (!stats) return []
    const totals = {}
    stats.forEach((row) => {
      if (!totals[row.college_school]) {
        totals[row.college_school] = {
          applicants: 0, admits: 0, enrolls: 0,
          rateSum: 0, count: 0, gpaMinSum: 0, gpaMaxSum: 0, gpaCount: 0,
        }
      }
      const t = totals[row.college_school]
      t.applicants += row.total_applicants || 0
      t.admits += row.total_admits || 0
      t.enrolls += row.total_enrolls || 0
      if (row.avg_admit_rate != null) { t.rateSum += row.avg_admit_rate; t.count++ }
      if (row.avg_admit_gpa_min != null) { t.gpaMinSum += parseFloat(row.avg_admit_gpa_min); t.gpaCount++ }
      if (row.avg_admit_gpa_max != null) { t.gpaMaxSum += parseFloat(row.avg_admit_gpa_max) }
    })
    return Object.entries(totals).map(([college, t]) => ({
      college,
      applicants: t.applicants,
      admits: t.admits,
      enrolls: t.enrolls,
      avgRate: t.count > 0 ? (t.rateSum / t.count).toFixed(1) : 'N/A',
      gpaRange: t.gpaCount > 0
        ? `${(t.gpaMinSum / t.gpaCount).toFixed(2)} - ${(t.gpaMaxSum / t.gpaCount).toFixed(2)}`
        : 'N/A',
    })).sort((a, b) => a.college.localeCompare(b.college))
  }, [stats])

  // Most / least competitive
  const validColleges = collegeTotals.filter((c) => c.avgRate !== 'N/A')
  const mostCompetitive = validColleges.length
    ? validColleges.reduce((a, b) => (parseFloat(a.avgRate) < parseFloat(b.avgRate) ? a : b))
    : null
  const leastCompetitive = validColleges.length
    ? validColleges.reduce((a, b) => (parseFloat(a.avgRate) > parseFloat(b.avgRate) ? a : b))
    : null

  const ucOptions = (universities || []).map((u) => ({ value: u, label: u }))

  return (
    <>
      <Title order={2} mb="md">School Stats{school ? `: ${school}` : ''}</Title>

      <FilterBar
        filters={[
          {
            type: 'select',
            label: 'Select UC',
            value: school || null,
            onChange: (val) => navigate(val ? `/school/${val}` : '/school'),
            data: ucOptions,
            placeholder: 'Pick a UC',
          },
        ]}
      />

      {!school && <Text c="dimmed">Select a UC above to view college-level statistics.</Text>}
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
            <StatsCard title="Colleges / Schools" value={colleges.length} />
            {mostCompetitive && (
              <StatsCard
                title="Most Competitive"
                value={mostCompetitive.college}
                subtitle={`${mostCompetitive.avgRate}% avg admit rate`}
              />
            )}
            {leastCompetitive && (
              <StatsCard
                title="Least Competitive"
                value={leastCompetitive.college}
                subtitle={`${leastCompetitive.avgRate}% avg admit rate`}
              />
            )}
            <StatsCard
              title="Total Applicants"
              value={collegeTotals.reduce((s, c) => s + c.applicants, 0).toLocaleString()}
            />
          </SimpleGrid>

          <Title order={4} mb="sm">By College / School</Title>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>College / School</Table.Th>
                <Table.Th>Applicants</Table.Th>
                <Table.Th>Admits</Table.Th>
                <Table.Th>Avg Admit Rate</Table.Th>
                <Table.Th>GPA Range</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {collegeTotals.map((row) => (
                <Table.Tr key={row.college}>
                  <Table.Td>{row.college}</Table.Td>
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
