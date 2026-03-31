import { useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Title, SimpleGrid, Table, Loader, Alert, Text,
  Paper, UnstyledButton, Group, Button, Stack, Badge, ActionIcon, TextInput,
} from '@mantine/core'
import { IconSearch } from '@tabler/icons-react'
import { IconStar, IconStarFilled } from '@tabler/icons-react'
import { useMajorStats, useGroupedMajors } from '../hooks/useApi'
import { useSavedCombos } from '../hooks/useUserData'
import StatsCard from '../components/StatsCard'
import TrendChart from '../components/TrendChart'
import { UC_COLORS } from '../utils/ucColors'

export default function MajorStats() {
  const { '*': splatParam } = useParams()
  const navigate = useNavigate()
  const { data: groupedMajors, loading: majorsLoading } = useGroupedMajors()
  const decodedMajor = splatParam ? decodeURIComponent(splatParam) : null
  const { data: stats, loading, error } = useMajorStats(decodedMajor)
  const groupedByLetter = useMemo(() => {
    if (!groupedMajors) return {}
    const groups = {}
    groupedMajors.forEach((m) => {
      const letter = m.name[0].toUpperCase()
      if (!groups[letter]) groups[letter] = []
      groups[letter].push(m)
    })
    Object.values(groups).forEach((arr) => arr.sort((a, b) => a.name.localeCompare(b.name)))
    return groups
  }, [groupedMajors])

  const letters = Object.keys(groupedByLetter).sort()

  const relatedMajors = useMemo(() => {
    if (!groupedMajors || !decodedMajor) return []
    const group = groupedMajors.find((g) => g.name === decodedMajor)
    if (group) return group.related
    const parent = groupedMajors.find((g) => g.related.some((r) => r.name === decodedMajor))
    if (parent) {
      return [
        { name: parent.name, campuses: parent.campuses, latest_year: parent.latest_year },
        ...parent.related.filter((r) => r.name !== decodedMajor),
      ]
    }
    return []
  }, [groupedMajors, decodedMajor])

  const [searchQuery, setSearchQuery] = useState('')
  const [selectedUCs, setSelectedUCs] = useState([])
  const [yAxis, setYAxis] = useState('admitRate')

  const allUniversities = useMemo(() => {
    if (!stats) return []
    return [...new Set(stats.map((s) => s.university))].sort()
  }, [stats])

  const activeUCs = selectedUCs.length > 0 ? selectedUCs : allUniversities

  const chartData = useMemo(() => {
    if (!stats) return []
    const byYear = {}
    stats.forEach((row) => {
      if (!activeUCs.includes(row.university)) return
      if (!byYear[row.year]) byYear[row.year] = { year: row.year }
      if (yAxis === 'gpa') {
        if (row.avg_admit_gpa_min != null) {
          byYear[row.year][row.university] = parseFloat(row.avg_admit_gpa_min)
        }
      } else {
        byYear[row.year][row.university] = row.avg_admit_rate != null
          ? Math.round(row.avg_admit_rate * 10) / 10
          : null
      }
    })
    return Object.values(byYear).sort((a, b) => a.year - b.year)
  }, [stats, activeUCs, yAxis])

  const chartSeries = activeUCs.map((u) => ({ key: u, label: u }))

  const uniTotals = useMemo(() => {
    if (!stats) return []
    const totals = {}
    stats.forEach((row) => {
      if (!activeUCs.includes(row.university)) return
      if (!totals[row.university]) {
        totals[row.university] = {
          applicants: 0, admits: 0, enrolls: 0,
          rateSum: 0, count: 0,
          latestGpaYear: 0, latestGpaMin: null, latestGpaMax: null,
        }
      }
      const t = totals[row.university]
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
    return Object.entries(totals).map(([uni, t]) => ({
      university: uni,
      applicants: t.applicants,
      admits: t.admits,
      enrolls: t.enrolls,
      avgRate: t.count > 0 ? (t.rateSum / t.count).toFixed(1) : 'N/A',
      gpaRange: t.latestGpaMin != null
        ? `${t.latestGpaMin.toFixed(2)} - ${t.latestGpaMax != null ? t.latestGpaMax.toFixed(2) : '?'} (${t.latestGpaYear})`
        : 'N/A',
    })).sort((a, b) => a.university.localeCompare(b.university))
  }, [stats, activeUCs])

  const validUnis = uniTotals.filter((u) => u.avgRate !== 'N/A')
  const mostCompetitive = validUnis.length
    ? validUnis.reduce((a, b) => (parseFloat(a.avgRate) < parseFloat(b.avgRate) ? a : b))
    : null
  const leastCompetitive = validUnis.length
    ? validUnis.reduce((a, b) => (parseFloat(a.avgRate) > parseFloat(b.avgRate) ? a : b))
    : null

  const filteredByLetter = useMemo(() => {
    if (!searchQuery.trim()) return groupedByLetter
    const q = searchQuery.toLowerCase()
    const filtered = {}
    for (const [letter, majors] of Object.entries(groupedByLetter)) {
      const matches = majors.filter((m) => m.name.toLowerCase().includes(q))
      if (matches.length > 0) filtered[letter] = matches
    }
    return filtered
  }, [groupedByLetter, searchQuery])

  const filteredLetters = Object.keys(filteredByLetter).sort()

  if (!decodedMajor) {
    return (
      <>
        <Title order={2} mb="md">By Major</Title>

        <TextInput
          placeholder="Search majors..."
          leftSection={<IconSearch size={16} />}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.currentTarget.value)}
          mb="md"
        />

        <Group gap={6} mb="lg">
          {filteredLetters.map((letter) => (
            <Button
              key={letter}
              size="compact-xs"
              variant="subtle"
              color="blue"
              onClick={() => document.getElementById(`letter-${letter}`)?.scrollIntoView({ behavior: 'smooth' })}
            >
              {letter}
            </Button>
          ))}
        </Group>

        {majorsLoading && <Loader m="xl" />}

        <Stack gap="xl">
          {filteredLetters.map((letter) => (
            <div key={letter} id={`letter-${letter}`}>
              <Title order={4} mb="xs" c="blue">{letter}</Title>
              <SimpleGrid cols={{ base: 2, sm: 3, md: 4 }}>
                {filteredByLetter[letter].map((m) => {
                  const visibleRelated = m.related
                  return (
                  <UnstyledButton key={m.name} onClick={() => navigate(`/major/${encodeURIComponent(m.name)}`)}>
                    <Paper
                      withBorder
                      p="sm"
                      radius="md"
                      style={{ cursor: 'pointer', transition: 'box-shadow 150ms' }}
                      onMouseEnter={(e) => { e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)' }}
                      onMouseLeave={(e) => { e.currentTarget.style.boxShadow = '' }}
                    >
                      <Text size="sm" fw={500}>{m.name}</Text>
                      {visibleRelated.length > 0 && (
                        <Text size="xs" c="dimmed" mb={4}>+{visibleRelated.length} specialization{visibleRelated.length > 1 ? 's' : ''}</Text>
                      )}
                      {m.campuses && m.campuses.length > 0 && (
                        <Group gap={4} mt={4}>
                          {m.campuses.map((c) => (
                            <Badge
                              key={c}
                              size="xs"
                              variant="light"
                              style={{
                                color: UC_COLORS[c] || '#666',
                                borderColor: UC_COLORS[c] || '#666',
                                backgroundColor: `${UC_COLORS[c] || '#666'}15`,
                              }}
                            >
                              {c}
                            </Badge>
                          ))}
                        </Group>
                      )}
                    </Paper>
                  </UnstyledButton>
                  )
                })}
              </SimpleGrid>
            </div>
          ))}
        </Stack>
      </>
    )
  }

  return (
    <MajorDetailView
      decodedMajor={decodedMajor} navigate={navigate} relatedMajors={relatedMajors}
      loading={loading} error={error} stats={stats} chartData={chartData} chartSeries={chartSeries}
      activeUCs={activeUCs} mostCompetitive={mostCompetitive} leastCompetitive={leastCompetitive}
      uniTotals={uniTotals} yAxis={yAxis} setYAxis={setYAxis}
    />
  )
}

function MajorDetailView({ decodedMajor, navigate, relatedMajors, loading, error, stats,
  chartData, chartSeries, activeUCs, mostCompetitive, leastCompetitive, uniTotals, yAxis, setYAxis }) {
  const { saveCombo, unsaveCombo, isComboSaved } = useSavedCombos()

  return (
    <>
      <Title order={2} mb="md">Major Stats: {decodedMajor}</Title>
      <Text
        c="dimmed"
        size="sm"
        mb="md"
        style={{ cursor: 'pointer' }}
        onClick={() => navigate('/major')}
      >
        &larr; Back to all majors
      </Text>

      {relatedMajors.length > 0 && (
        <>
          <Title order={4} mb="sm">Related Specializations</Title>
          <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} mb="lg">
            {relatedMajors.map((rm) => (
              <UnstyledButton key={rm.name} onClick={() => navigate(`/major/${encodeURIComponent(rm.name)}`)}>
                <Paper
                  withBorder
                  p="sm"
                  radius="md"
                  style={{ cursor: 'pointer', transition: 'box-shadow 150ms' }}
                  onMouseEnter={(e) => { e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)' }}
                  onMouseLeave={(e) => { e.currentTarget.style.boxShadow = '' }}
                >
                  <Text size="sm">{rm.name}</Text>
                  {rm.campuses && rm.campuses.length > 0 && (
                    <Group gap={4} mt={4}>
                      {rm.campuses.map((c) => (
                        <Badge
                          key={c}
                          size="xs"
                          variant="light"
                          style={{
                            color: UC_COLORS[c] || '#666',
                            borderColor: UC_COLORS[c] || '#666',
                            backgroundColor: `${UC_COLORS[c] || '#666'}15`,
                          }}
                        >
                          {c}
                        </Badge>
                      ))}
                    </Group>
                  )}
                </Paper>
              </UnstyledButton>
            ))}
          </SimpleGrid>
        </>
      )}

      {loading && <Loader m="xl" />}
      {error && <Alert color="red" title="Error">{error}</Alert>}

      {stats && (
        <>
          <TrendChart
            data={chartData}
            xKey="year"
            series={chartSeries}
            colorMap={UC_COLORS}
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
            <StatsCard title="UCs Offering This Major" value={activeUCs.length} />
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
                <Table.Th></Table.Th>
                <Table.Th>University</Table.Th>
                <Table.Th>Applicants</Table.Th>
                <Table.Th>Admits</Table.Th>
                <Table.Th>Avg Admit Rate</Table.Th>
                <Table.Th>GPA Range (25th-75th Percentile)</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {uniTotals.map((row) => {
                const saved = isComboSaved(decodedMajor, row.university)
                return (
                  <Table.Tr key={row.university}>
                    <Table.Td>
                      <ActionIcon
                        variant="subtle"
                        color="yellow"
                        size="sm"
                        onClick={() => saved
                          ? unsaveCombo(decodedMajor, row.university)
                          : saveCombo(decodedMajor, row.university)
                        }
                        title={saved ? 'Remove from saved' : `Save ${decodedMajor} @ ${row.university}`}
                      >
                        {saved ? <IconStarFilled size={16} /> : <IconStar size={16} />}
                      </ActionIcon>
                    </Table.Td>
                    <Table.Td>{row.university}</Table.Td>
                    <Table.Td>{row.applicants.toLocaleString()}</Table.Td>
                    <Table.Td>{row.admits.toLocaleString()}</Table.Td>
                    <Table.Td>{row.avgRate}%</Table.Td>
                    <Table.Td>{row.gpaRange}</Table.Td>
                  </Table.Tr>
                )
              })}
            </Table.Tbody>
          </Table>
        </>
      )}

    </>
  )
}
