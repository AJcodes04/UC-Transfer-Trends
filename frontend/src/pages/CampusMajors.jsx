import { useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Title, SimpleGrid, Table, Loader, Alert, Paper, Image, Text, UnstyledButton, Switch, Group,
} from '@mantine/core'
import { useCampusMajorStats } from '../hooks/useApi'
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

export default function CampusMajors() {
  const { campus } = useParams()
  const navigate = useNavigate()
  const { data: stats, loading, error } = useCampusMajorStats(campus)
  const [hideDiscontinued, setHideDiscontinued] = useState(true)

  const DISCONTINUED_BEFORE = 2022

  // Build per-major metadata: latest year, year count, total applicants
  const majorInfo = useMemo(() => {
    if (!stats) return {}
    const info = {}
    stats.forEach((row) => {
      if (!info[row.major_name]) info[row.major_name] = { latestYear: 0, years: new Set(), apps: 0 }
      const m = info[row.major_name]
      m.latestYear = Math.max(m.latestYear, row.year)
      m.years.add(row.year)
      m.apps += row.total_applicants || 0
    })
    return info
  }, [stats])

  // A major is "discontinued junk" if it has no data from 2020+ AND only 1 year of data
  const isDiscontinuedJunk = (name) => {
    const m = majorInfo[name]
    return m && m.latestYear < DISCONTINUED_BEFORE && m.years.size <= 1
  }

  // All majors at this campus (filtered when toggle is on)
  const allMajors = useMemo(() => {
    if (!stats) return []
    const names = [...new Set(stats.map((s) => s.major_name))].sort()
    if (hideDiscontinued) return names.filter((n) => !isDiscontinuedJunk(n))
    return names
  }, [stats, majorInfo, hideDiscontinued])

  // Top 20 majors by total applicants for the chart (respects filter)
  const topMajors = useMemo(() => {
    const validSet = new Set(allMajors)
    return Object.entries(majorInfo)
      .filter(([name]) => validSet.has(name))
      .sort((a, b) => b[1].apps - a[1].apps)
      .slice(0, 20)
      .map(([name]) => name)
  }, [allMajors, majorInfo])

  // Pivot for chart: one row per year, one key per major (top 20 only)
  const chartData = useMemo(() => {
    if (!stats) return []
    const topSet = new Set(topMajors)
    const byYear = {}
    stats.forEach((row) => {
      if (!topSet.has(row.major_name)) return
      if (!byYear[row.year]) byYear[row.year] = { year: row.year }
      byYear[row.year][row.major_name] = row.avg_admit_rate != null
        ? Math.round(row.avg_admit_rate * 10) / 10
        : null
    })
    return Object.values(byYear).sort((a, b) => a.year - b.year)
  }, [stats, topMajors])

  const chartSeries = topMajors.map((m) => ({ key: m, label: m }))

  // Per-major aggregate stats (filtered by toggle)
  const majorTotals = useMemo(() => {
    if (!stats) return []
    const validSet = new Set(allMajors)
    const totals = {}
    stats.forEach((row) => {
      if (!validSet.has(row.major_name)) return
      if (!totals[row.major_name]) {
        totals[row.major_name] = {
          applicants: 0, admits: 0, enrolls: 0,
          rateSum: 0, count: 0, gpaMinSum: 0, gpaMaxSum: 0, gpaCount: 0,
        }
      }
      const t = totals[row.major_name]
      t.applicants += row.total_applicants || 0
      t.admits += row.total_admits || 0
      t.enrolls += row.total_enrolls || 0
      if (row.avg_admit_rate != null) { t.rateSum += row.avg_admit_rate; t.count++ }
      if (row.avg_admit_gpa_min != null) { t.gpaMinSum += parseFloat(row.avg_admit_gpa_min); t.gpaCount++ }
      if (row.avg_admit_gpa_max != null) { t.gpaMaxSum += parseFloat(row.avg_admit_gpa_max) }
    })
    return Object.entries(totals).map(([major, t]) => ({
      major,
      applicants: t.applicants,
      admits: t.admits,
      enrolls: t.enrolls,
      avgRate: t.count > 0 ? (t.rateSum / t.count).toFixed(1) : 'N/A',
      gpaRange: t.gpaCount > 0
        ? `${(t.gpaMinSum / t.gpaCount).toFixed(2)} - ${(t.gpaMaxSum / t.gpaCount).toFixed(2)}`
        : 'N/A',
    })).sort((a, b) => a.major.localeCompare(b.major))
  }, [stats, allMajors])

  // Most / least competitive major
  const validMajors = majorTotals.filter((m) => m.avgRate !== 'N/A')
  const mostCompetitive = validMajors.length
    ? validMajors.reduce((a, b) => (parseFloat(a.avgRate) < parseFloat(b.avgRate) ? a : b))
    : null
  const leastCompetitive = validMajors.length
    ? validMajors.reduce((a, b) => (parseFloat(a.avgRate) > parseFloat(b.avgRate) ? a : b))
    : null

  const campusName = CAMPUSES.find((c) => c.code === campus)?.name || campus

  // Landing view — no campus selected
  if (!campus) {
    return (
      <>
        <Title order={2} mb="md">By Campus</Title>
        <Text c="dimmed" mb="lg">Select a campus to view all its majors and admit rate trends.</Text>
        <SimpleGrid cols={{ base: 2, sm: 3, md: 4 }}>
          {CAMPUSES.map((c) => (
            <UnstyledButton key={c.code} onClick={() => navigate(`/campus/${c.code}`)}>
              <Paper
                withBorder
                p="lg"
                radius="md"
                style={{ textAlign: 'center', cursor: 'pointer', transition: 'box-shadow 150ms' }}
                onMouseEnter={(e) => { e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)' }}
                onMouseLeave={(e) => { e.currentTarget.style.boxShadow = '' }}
              >
                <Image
                  src={c.logo}
                  alt={c.name}
                  h={80}
                  w="auto"
                  fit="contain"
                  mx="auto"
                  mb="sm"
                />
                <Text fw={600} size="sm">{c.name}</Text>
              </Paper>
            </UnstyledButton>
          ))}
        </SimpleGrid>
      </>
    )
  }

  // Detail view — campus selected
  return (
    <>
      <Title order={2} mb="md">Campus Majors: {campusName}</Title>
      <Group justify="space-between" mb="md">
        <Text
          c="dimmed"
          size="sm"
          style={{ cursor: 'pointer' }}
          onClick={() => navigate('/campus')}
        >
          &larr; Back to all campuses
        </Text>
        <Switch
          label="Hide discontinued majors"
          checked={hideDiscontinued}
          onChange={(e) => setHideDiscontinued(e.currentTarget.checked)}
          size="sm"
        />
      </Group>

      {loading && <Loader m="xl" />}
      {error && <Alert color="red" title="Error">{error}</Alert>}

      {stats && (
        <>
          <Title order={4} mb="xs">Top 20 Majors by Applicants</Title>
          <TrendChart
            data={chartData}
            xKey="year"
            series={chartSeries}
            yLabel="Avg Admit Rate (%)"
          />

          <SimpleGrid cols={{ base: 1, sm: 2, md: 4 }} mt="lg" mb="lg">
            <StatsCard title="Majors Offered" value={allMajors.length} />
            {mostCompetitive && (
              <StatsCard
                title="Most Competitive"
                value={mostCompetitive.major}
                subtitle={`${mostCompetitive.avgRate}% avg admit rate`}
              />
            )}
            {leastCompetitive && (
              <StatsCard
                title="Least Competitive"
                value={leastCompetitive.major}
                subtitle={`${leastCompetitive.avgRate}% avg admit rate`}
              />
            )}
            <StatsCard
              title="Total Applicants"
              value={majorTotals.reduce((s, m) => s + m.applicants, 0).toLocaleString()}
            />
          </SimpleGrid>

          <Title order={4} mb="sm">By Major</Title>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Major</Table.Th>
                <Table.Th>Applicants</Table.Th>
                <Table.Th>Admits</Table.Th>
                <Table.Th>Avg Admit Rate</Table.Th>
                <Table.Th>GPA Range</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {majorTotals.map((row) => (
                <Table.Tr key={row.major}>
                  <Table.Td>{row.major}</Table.Td>
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
