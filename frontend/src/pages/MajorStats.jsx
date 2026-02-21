import { useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Title, SimpleGrid, Table, Loader, Alert, Text,
  Paper, UnstyledButton, Group, Button, Stack, Badge,
} from '@mantine/core'
import { useMajorStats, useGroupedMajors } from '../hooks/useApi'
import StatsCard from '../components/StatsCard'
import TrendChart from '../components/TrendChart'
import { UC_COLORS } from '../utils/ucColors'

export default function MajorStats() {
  const { major } = useParams()
  const navigate = useNavigate()
  const { data: groupedMajors, loading: majorsLoading } = useGroupedMajors()
  const decodedMajor = major ? decodeURIComponent(major) : null
  const { data: stats, loading, error } = useMajorStats(decodedMajor)

  // Group base majors alphabetically by first letter
  const groupedByLetter = useMemo(() => {
    if (!groupedMajors) return {}
    const groups = {}
    groupedMajors.forEach((m) => {
      const letter = m.name[0].toUpperCase()
      if (!groups[letter]) groups[letter] = []
      groups[letter].push(m)
    })
    // Sort each letter group alphabetically
    Object.values(groups).forEach((arr) => arr.sort((a, b) => a.name.localeCompare(b.name)))
    return groups
  }, [groupedMajors])

  const letters = Object.keys(groupedByLetter).sort()

  // Find related majors for the currently selected major
  const relatedMajors = useMemo(() => {
    if (!groupedMajors || !decodedMajor) return []
    const group = groupedMajors.find((g) => g.name === decodedMajor)
    if (group) return group.related
    // If the selected major is itself a sub-major, find its parent
    const parent = groupedMajors.find((g) => g.related.includes(decodedMajor))
    if (parent) {
      return [parent.name, ...parent.related.filter((r) => r !== decodedMajor)]
    }
    return []
  }, [groupedMajors, decodedMajor])

  // --- Detail view state ---
  const [selectedUCs, setSelectedUCs] = useState([])

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
      byYear[row.year][row.university] = row.avg_admit_rate != null
        ? Math.round(row.avg_admit_rate * 10) / 10
        : null
    })
    return Object.values(byYear).sort((a, b) => a.year - b.year)
  }, [stats, activeUCs])

  const chartSeries = activeUCs.map((u) => ({ key: u, label: u }))

  const uniTotals = useMemo(() => {
    if (!stats) return []
    const totals = {}
    stats.forEach((row) => {
      if (!activeUCs.includes(row.university)) return
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
  }, [stats, activeUCs])

  const validUnis = uniTotals.filter((u) => u.avgRate !== 'N/A')
  const mostCompetitive = validUnis.length
    ? validUnis.reduce((a, b) => (parseFloat(a.avgRate) < parseFloat(b.avgRate) ? a : b))
    : null
  const leastCompetitive = validUnis.length
    ? validUnis.reduce((a, b) => (parseFloat(a.avgRate) > parseFloat(b.avgRate) ? a : b))
    : null

  // Landing view — no major selected
  if (!decodedMajor) {
    return (
      <>
        <Title order={2} mb="md">By Major</Title>

        <Group gap={6} mb="lg">
          {letters.map((letter) => (
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
          {letters.map((letter) => (
            <div key={letter} id={`letter-${letter}`}>
              <Title order={4} mb="xs" c="blue">{letter}</Title>
              <SimpleGrid cols={{ base: 2, sm: 3, md: 4 }}>
                {groupedByLetter[letter].map((m) => (
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
                      {m.related.length > 0 && (
                        <Text size="xs" c="dimmed" mb={4}>+{m.related.length} specialization{m.related.length > 1 ? 's' : ''}</Text>
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
                ))}
              </SimpleGrid>
            </div>
          ))}
        </Stack>
      </>
    )
  }

  // Detail view — major selected
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

      {loading && <Loader m="xl" />}
      {error && <Alert color="red" title="Error">{error}</Alert>}

      {stats && (
        <>
          <TrendChart
            data={chartData}
            xKey="year"
            series={chartSeries}
            colorMap={UC_COLORS}
            yLabel="Avg Admit Rate (%)"
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

      {relatedMajors.length > 0 && (
        <>
          <Title order={4} mt="xl" mb="sm">Related Specializations</Title>
          <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }}>
            {relatedMajors.map((rm) => (
              <UnstyledButton key={rm} onClick={() => navigate(`/major/${encodeURIComponent(rm)}`)}>
                <Paper
                  withBorder
                  p="sm"
                  radius="md"
                  style={{ cursor: 'pointer', transition: 'box-shadow 150ms' }}
                  onMouseEnter={(e) => { e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)' }}
                  onMouseLeave={(e) => { e.currentTarget.style.boxShadow = '' }}
                >
                  <Text size="sm">{rm}</Text>
                </Paper>
              </UnstyledButton>
            ))}
          </SimpleGrid>
        </>
      )}
    </>
  )
}
