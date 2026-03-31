import { useState, useMemo, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Title, SimpleGrid, Table, Loader, Alert, Paper, Image, Text, UnstyledButton, Slider, Group } from '@mantine/core'
import { useSchoolStats } from '../hooks/useApi'
import StatsCard from '../components/StatsCard'
import TrendChart from '../components/TrendChart'

const CAMPUSES = [
  { code: 'UCB',  name: 'UC Berkeley',       logo: '/berkeleylogo.png' },
  { code: 'UCD',  name: 'UC Davis',          logo: '/ucdlogo.png' },
  { code: 'UCI',  name: 'UC Irvine',         logo: '/ucilogo.png' },
  { code: 'UCLA', name: 'UCLA',              logo: '/uclalogo.png' },
  { code: 'UCM',  name: 'UC Merced',         logo: '/ucmlogo.png' },
  { code: 'UCR',  name: 'UC Riverside',      logo: '/ucrlogo.png' },
  { code: 'UCSB', name: 'UC Santa Barbara',  logo: '/ucsblogo.png' },
  { code: 'UCSC', name: 'UC Santa Cruz',     logo: '/ucsclogo.png' },
  { code: 'UCSD', name: 'UC San Diego',      logo: '/ucsdlogo.png' },
]

export default function SchoolStats() {
  const { school } = useParams()
  const navigate = useNavigate()
  const { data: stats, loading, error } = useSchoolStats(school)

  const [selectedColleges, setSelectedColleges] = useState([])
  const [selectedYear, setSelectedYear] = useState(null)

  const prevSchoolRef = useMemo(() => ({ current: school }), [])
  if (prevSchoolRef.current !== school) {
    prevSchoolRef.current = school
    if (selectedColleges.length) setSelectedColleges([])
  }

  const allColleges = useMemo(() => {
    if (!stats) return []
    return [...new Set(stats.map((s) => s.college_school))].sort()
  }, [stats])

  const activeColleges = selectedColleges.length > 0 ? selectedColleges : allColleges

  const chartData = useMemo(() => {
    if (!stats) return []
    const byYear = {}
    stats.forEach((row) => {
      if (!activeColleges.includes(row.college_school)) return
      if (!byYear[row.year]) byYear[row.year] = { year: row.year }
      byYear[row.year][row.college_school] = row.avg_admit_rate != null
        ? Math.round(row.avg_admit_rate * 10) / 10
        : null
    })
    return Object.values(byYear).sort((a, b) => a.year - b.year)
  }, [stats, activeColleges])

  const chartSeries = activeColleges.map((c) => ({ key: c, label: c }))

  const collegeTotals = useMemo(() => {
    if (!stats) return []
    const totals = {}
    stats.forEach((row) => {
      if (!activeColleges.includes(row.college_school)) return
      if (!totals[row.college_school]) {
        totals[row.college_school] = {
          applicants: 0, admits: 0, enrolls: 0,
          rateSum: 0, count: 0,
          latestGpaYear: 0, latestGpaMin: null, latestGpaMax: null,
        }
      }
      const t = totals[row.college_school]
      t.applicants += row.total_applicants || 0
      t.admits += row.total_admits || 0
      t.enrolls += row.total_enrolls || 0
      if (row.avg_admit_rate != null) { t.rateSum += row.avg_admit_rate; t.count++ }
      if (row.avg_admit_gpa_min != null && row.year > t.latestGpaYear) {
        t.latestGpaYear = row.year
        t.latestGpaMin = parseFloat(row.avg_admit_gpa_min)
        t.latestGpaMax = row.avg_admit_gpa_max != null ? parseFloat(row.avg_admit_gpa_max) : null
      }
    })
    return Object.entries(totals).map(([college, t]) => ({
      college,
      applicants: t.applicants,
      admits: t.admits,
      enrolls: t.enrolls,
      avgRate: t.count > 0 ? (t.rateSum / t.count).toFixed(1) : 'N/A',
      gpaRange: t.latestGpaMin != null
        ? `${t.latestGpaMin.toFixed(2)} - ${t.latestGpaMax != null ? t.latestGpaMax.toFixed(2) : '?'} (${t.latestGpaYear})`
        : 'N/A',
    })).sort((a, b) => a.college.localeCompare(b.college))
  }, [stats, activeColleges])

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

  const yearFilteredTotals = useMemo(() => {
    if (!stats || !selectedYear) return collegeTotals
    const filtered = stats.filter((row) => row.year === selectedYear && activeColleges.includes(row.college_school))
    const totals = {}
    filtered.forEach((row) => {
      if (!totals[row.college_school]) {
        totals[row.college_school] = {
          applicants: 0, admits: 0, enrolls: 0,
          rateSum: 0, count: 0,
          latestGpaMin: null, latestGpaMax: null,
        }
      }
      const t = totals[row.college_school]
      t.applicants += row.total_applicants || 0
      t.admits += row.total_admits || 0
      t.enrolls += row.total_enrolls || 0
      if (row.avg_admit_rate != null) { t.rateSum += row.avg_admit_rate; t.count++ }
      if (row.avg_admit_gpa_min != null) {
        t.latestGpaMin = parseFloat(row.avg_admit_gpa_min)
        t.latestGpaMax = row.avg_admit_gpa_max != null ? parseFloat(row.avg_admit_gpa_max) : null
      }
    })
    return Object.entries(totals).map(([college, t]) => ({
      college,
      applicants: t.applicants,
      admits: t.admits,
      enrolls: t.enrolls,
      avgRate: t.count > 0 ? (t.rateSum / t.count).toFixed(1) : 'N/A',
      gpaRange: t.latestGpaMin != null
        ? `${t.latestGpaMin.toFixed(2)} - ${t.latestGpaMax != null ? t.latestGpaMax.toFixed(2) : '?'}`
        : 'N/A',
    })).sort((a, b) => a.college.localeCompare(b.college))
  }, [stats, selectedYear, activeColleges, collegeTotals])

  const yearlyTotals = useMemo(() => {
    if (!stats) return { latest: null, prev: null }
    const byYear = {}
    stats.forEach((row) => {
      if (!activeColleges.includes(row.college_school)) return
      if (!byYear[row.year]) byYear[row.year] = { applicants: 0, admits: 0, enrolls: 0 }
      byYear[row.year].applicants += row.total_applicants || 0
      byYear[row.year].admits += row.total_admits || 0
      byYear[row.year].enrolls += row.total_enrolls || 0
    })
    const years = Object.keys(byYear).map(Number).sort((a, b) => b - a)
    return {
      latest: years[0] ? { year: years[0], ...byYear[years[0]] } : null,
      prev: years[1] ? { year: years[1], ...byYear[years[1]] } : null,
    }
  }, [stats, activeColleges])

  function yoyChange(latest, prev) {
    if (!latest || !prev || prev === 0) return null
    return ((latest - prev) / prev * 100).toFixed(1)
  }

  const validColleges = collegeTotals.filter((c) => c.avgRate !== 'N/A')
  const mostCompetitive = validColleges.length
    ? validColleges.reduce((a, b) => (parseFloat(a.avgRate) < parseFloat(b.avgRate) ? a : b))
    : null
  const leastCompetitive = validColleges.length
    ? validColleges.reduce((a, b) => (parseFloat(a.avgRate) > parseFloat(b.avgRate) ? a : b))
    : null

  if (!school) {
    return (
      <>
        <Title order={2} mb="md">By College/School</Title>
        <Text c="dimmed" mb="lg">Select a campus to view college/school-level statistics.</Text>
        <SimpleGrid cols={{ base: 2, sm: 3, md: 4 }}>
          {CAMPUSES.map((campus) => (
            <UnstyledButton key={campus.code} onClick={() => navigate(`/school/${campus.code}`)}>
              <Paper
                withBorder
                p="lg"
                radius="md"
                style={{ textAlign: 'center', cursor: 'pointer', transition: 'box-shadow 150ms' }}
                onMouseEnter={(e) => { e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)' }}
                onMouseLeave={(e) => { e.currentTarget.style.boxShadow = '' }}
              >
                <Image
                  src={campus.logo}
                  alt={campus.name}
                  h={80}
                  w="auto"
                  fit="contain"
                  mx="auto"
                  mb="sm"
                />
                <Text fw={600} size="sm">{campus.name}</Text>
              </Paper>
            </UnstyledButton>
          ))}
        </SimpleGrid>
      </>
    )
  }

  return (
    <>
      <Title order={2} mb="md">School Stats: {school}</Title>
      <Text
        c="dimmed"
        size="sm"
        mb="md"
        style={{ cursor: 'pointer' }}
        onClick={() => navigate('/school')}
      >
        &larr; Back to all campuses
      </Text>

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
            <StatsCard title="Colleges / Schools" value={activeColleges.length} />
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
              title={`Applicants (${yearlyTotals.latest?.year || ''})`}
              value={yearlyTotals.latest?.applicants.toLocaleString() || '-'}
              change={yoyChange(yearlyTotals.latest?.applicants, yearlyTotals.prev?.applicants)}
              subtitle={yearlyTotals.prev ? `vs ${yearlyTotals.prev.applicants.toLocaleString()} in ${yearlyTotals.prev.year}` : undefined}
            />
          </SimpleGrid>

          <Group justify="space-between" align="center" mb="sm">
            <Title order={4}>By College / School</Title>
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
                <Table.Th>College / School</Table.Th>
                <Table.Th>Applicants</Table.Th>
                <Table.Th>Admits</Table.Th>
                <Table.Th>Admit Rate</Table.Th>
                <Table.Th>GPA Range (25th-75th Percentile)</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {yearFilteredTotals.map((row) => (
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
