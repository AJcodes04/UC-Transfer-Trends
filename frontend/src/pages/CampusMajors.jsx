import { useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Title, SimpleGrid, Table, Loader, Alert, Paper, Image, Text, UnstyledButton, Group,
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
  const [yAxis, setYAxis] = useState('admitRate')
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

  const allMajors = useMemo(() => {
    if (!stats) return []
    return [...new Set(stats.map((s) => s.major_name))].sort()
  }, [stats])

  const topMajors = useMemo(() => {
    const validSet = new Set(allMajors)
    return Object.entries(majorInfo)
      .filter(([name]) => validSet.has(name))
      .sort((a, b) => b[1].apps - a[1].apps)
      .slice(0, 20)
      .map(([name]) => name)
  }, [allMajors, majorInfo])

  const chartData = useMemo(() => {
    if (!stats) return []
    const topSet = new Set(topMajors)
    const byYear = {}
    stats.forEach((row) => {
      if (!topSet.has(row.major_name)) return
      if (!byYear[row.year]) byYear[row.year] = { year: row.year }
      if (yAxis === 'gpa') {
        if (row.avg_admit_gpa_min != null) {
          byYear[row.year][row.major_name] = parseFloat(row.avg_admit_gpa_min)
        }
      } else {
        byYear[row.year][row.major_name] = row.avg_admit_rate != null
          ? Math.round(row.avg_admit_rate * 10) / 10
          : null
      }
    })
    return Object.values(byYear).sort((a, b) => a.year - b.year)
  }, [stats, topMajors, yAxis])

  const chartSeries = topMajors.map((m) => ({ key: m, label: m }))

  const majorTotals = useMemo(() => {
    if (!stats) return []
    const validSet = new Set(allMajors)
    const totals = {}
    stats.forEach((row) => {
      if (!validSet.has(row.major_name)) return
      if (!totals[row.major_name]) {
        totals[row.major_name] = {
          applicants: 0, admits: 0, enrolls: 0,
          rateSum: 0, count: 0,
          latestRateYear: 0, latestRate: null,
          gpaMinSum: 0, gpaCount: 0,
          latestGpaYear: 0, latestGpaMin: null, latestGpaMax: null,
        }
      }
      const t = totals[row.major_name]
      t.applicants += row.total_applicants || 0
      t.admits += row.total_admits || 0
      t.enrolls += row.total_enrolls || 0
      if (row.avg_admit_rate != null) {
        t.rateSum += row.avg_admit_rate; t.count++
        if (row.year > t.latestRateYear) {
          t.latestRateYear = row.year
          t.latestRate = row.avg_admit_rate
        }
      }
      if (row.avg_admit_gpa_min != null) {
        t.gpaMinSum += parseFloat(row.avg_admit_gpa_min)
        t.gpaCount++
        if (row.year > t.latestGpaYear) {
          t.latestGpaYear = row.year
          t.latestGpaMin = parseFloat(row.avg_admit_gpa_min)
          t.latestGpaMax = row.avg_admit_gpa_max != null ? parseFloat(row.avg_admit_gpa_max) : null
        }
      }
    })
    return Object.entries(totals).map(([major, t]) => ({
      major,
      applicants: t.applicants,
      admits: t.admits,
      enrolls: t.enrolls,
      avgRate: t.count > 0 ? (t.rateSum / t.count).toFixed(1) : 'N/A',
      latestRate: t.latestRate != null ? `${Math.round(t.latestRate * 10) / 10}%` : 'N/A',
      avgGpa: t.gpaCount > 0 ? (t.gpaMinSum / t.gpaCount).toFixed(2) : 'N/A',
      latestGpaRange: t.latestGpaMin != null
        ? `${t.latestGpaMin.toFixed(2)} - ${t.latestGpaMax != null ? t.latestGpaMax.toFixed(2) : '?'}`
        : 'N/A',
    })).sort((a, b) => a.major.localeCompare(b.major))
  }, [stats, allMajors])

  const validMajors = majorTotals.filter((m) => m.avgRate !== 'N/A')
  const mostCompetitive = validMajors.length
    ? validMajors.reduce((a, b) => (parseFloat(a.avgRate) < parseFloat(b.avgRate) ? a : b))
    : null
  const leastCompetitive = validMajors.length
    ? validMajors.reduce((a, b) => (parseFloat(a.avgRate) > parseFloat(b.avgRate) ? a : b))
    : null


  const campusName = CAMPUSES.find((c) => c.code === campus)?.name || campus

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

  return (
    <>
      <Title order={2} mb="md">Campus Majors: {campusName}</Title>
      <Text
        c="dimmed"
        size="sm"
        mb="md"
        style={{ cursor: 'pointer' }}
        onClick={() => navigate('/campus')}
      >
        &larr; Back to all campuses
      </Text>

      {loading && <Loader m="xl" />}
      {error && <Alert color="red" title="Error">{error}</Alert>}

      {stats && (
        <>
          <Title order={4} mb="xs">Top 20 Majors by Applicants</Title>
          <TrendChart
            data={chartData}
            xKey="year"
            series={chartSeries}
            yLabel={yAxis === 'gpa' ? 'Lowest GPA (25th percentile)' : 'Avg Admit Rate (%)'}
            yAxisOptions={[
              { value: 'admitRate', label: 'Admit Rate (%)' },
              { value: 'gpa', label: 'Lowest GPA (25th percentile)' },
            ]}
            onYAxisChange={setYAxis}
            yDomain={yAxis === 'gpa' ? [2.4, 4.0] : undefined}
            tooltipSuffix={yAxis === 'gpa' ? '' : '%'}
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
          <Table striped highlightOnHover stickyHeader stickyHeaderOffset={0}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Major</Table.Th>
                <Table.Th>Applicants</Table.Th>
                <Table.Th>Admits</Table.Th>
                <Table.Th>Enrolls</Table.Th>
                <Table.Th>Avg Admit Rate</Table.Th>
                <Table.Th>Latest Admit Rate</Table.Th>
                <Table.Th>Yield Rate</Table.Th>
                <Table.Th>Latest GPA Range</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {majorTotals.map((row) => (
                <Table.Tr key={row.major}>
                  <Table.Td>{row.major}</Table.Td>
                  <Table.Td>{row.applicants.toLocaleString()}</Table.Td>
                  <Table.Td>{row.admits.toLocaleString()}</Table.Td>
                  <Table.Td>{row.enrolls.toLocaleString()}</Table.Td>
                  <Table.Td>{row.avgRate}%</Table.Td>
                  <Table.Td>{row.latestRate}</Table.Td>
                  <Table.Td>{row.admits > 0 ? `${Math.round(row.enrolls / row.admits * 100)}%` : 'N/A'}</Table.Td>
                  <Table.Td>{row.latestGpaRange}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </>
      )}
    </>
  )
}
