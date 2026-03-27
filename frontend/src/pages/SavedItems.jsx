import { useState, useMemo, useEffect } from 'react'
import {
  Title, Text, SimpleGrid, Paper, Group, Badge, ActionIcon,
  Stack, Loader, Table, Divider,
} from '@mantine/core'
import { IconX } from '@tabler/icons-react'
import axios from 'axios'
import { useSavedCombos, useGPA } from '../hooks/useUserData'
import { UC_COLORS } from '../utils/ucColors'
import StatsCard from '../components/StatsCard'
import TrendChart from '../components/TrendChart'

export default function SavedItems() {
  const { savedCombos, unsaveCombo } = useSavedCombos()
  const userGPA = useGPA()

  const uniqueMajors = useMemo(
    () => [...new Set(savedCombos.map((c) => c.major))],
    [savedCombos]
  )

  const [statsByMajor, setStatsByMajor] = useState({})
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (uniqueMajors.length === 0) { setStatsByMajor({}); return }
    let cancelled = false
    setLoading(true)

    Promise.all(
      uniqueMajors.map((major) =>
        axios.get(`/api/stats/by-major/${encodeURIComponent(major)}/`)
          .then((res) => ({ major, data: res.data }))
          .catch(() => ({ major, data: [] }))
      )
    ).then((results) => {
      if (cancelled) return
      const map = {}
      results.forEach(({ major, data }) => { map[major] = data })
      setStatsByMajor(map)
      setLoading(false)
    })

    return () => { cancelled = true }
  }, [uniqueMajors.join('|||')])

  const comboData = useMemo(() => {
    return savedCombos.map((combo) => {
      const rows = (statsByMajor[combo.major] || []).filter(
        (r) => r.university === combo.school
      )
      if (rows.length === 0) return { ...combo, hasData: false }

      const maxYear = Math.max(...rows.map((r) => r.year))
      const recentRows = rows.filter((r) => r.year === maxYear)
      const mins = recentRows.filter((r) => r.avg_admit_gpa_min != null).map((r) => parseFloat(r.avg_admit_gpa_min))
      const maxes = recentRows.filter((r) => r.avg_admit_gpa_max != null).map((r) => parseFloat(r.avg_admit_gpa_max))
      const gpaMin = mins.length > 0 ? Math.min(...mins) : null
      const gpaMax = maxes.length > 0 ? Math.max(...maxes) : null

      const totalApps = rows.reduce((s, r) => s + (r.total_applicants || 0), 0)
      const totalAdmits = rows.reduce((s, r) => s + (r.total_admits || 0), 0)
      const rates = rows.filter((r) => r.avg_admit_rate != null)
      const avgRate = rates.length > 0
        ? (rates.reduce((s, r) => s + r.avg_admit_rate, 0) / rates.length).toFixed(1)
        : null

      return { ...combo, hasData: true, gpaMin, gpaMax, gpaYear: maxYear, totalApps, totalAdmits, avgRate }
    })
  }, [savedCombos, statsByMajor])

  const { chartData, chartSeries } = useMemo(() => {
    if (savedCombos.length === 0) return { chartData: [], chartSeries: [] }
    const byYear = {}
    const seriesKeys = []

    for (const combo of savedCombos) {
      const rows = (statsByMajor[combo.major] || []).filter(
        (r) => r.university === combo.school
      )
      const key = `${combo.major} @ ${combo.school}`
      if (rows.length === 0) continue
      seriesKeys.push({ key, label: key, school: combo.school })

      for (const row of rows) {
        if (row.avg_admit_rate == null) continue
        if (!byYear[row.year]) byYear[row.year] = { year: row.year }
        byYear[row.year][key] = Math.round(row.avg_admit_rate * 10) / 10
      }
    }

    const data = Object.values(byYear).sort((a, b) => a.year - b.year)
    return { chartData: data, chartSeries: seriesKeys }
  }, [savedCombos, statsByMajor])

  const colorMap = useMemo(() => {
    const map = {}
    for (const s of chartSeries) {
      map[s.key] = UC_COLORS[s.school] || '#666'
    }
    return map
  }, [chartSeries])

  function gpaStatus(gpaMin, gpaMax) {
    if (userGPA == null || gpaMin == null) return null
    if (userGPA >= gpaMax) return 'above'
    if (userGPA >= gpaMin) return 'within'
    return 'below'
  }
  const statusColor = { above: 'green', within: 'yellow', below: 'red' }
  const statusLabel = { above: 'Above', within: 'Within', below: 'Below' }

  if (savedCombos.length === 0) {
    return (
      <>
        <Title order={2} mb="md">Saved Schools</Title>
        <Text c="dimmed" ta="center" mt="xl">
          No saved items yet. Go to By Major, pick a major, and star the UC campuses you want to compare.
        </Text>
      </>
    )
  }

  return (
    <>
      <Title order={2} mb="md">Saved Schools</Title>
      <Text c="dimmed" size="sm" mb="lg">
        Your saved major + school combinations. Each card shows the most recent admit GPA range for that specific major at that school.
      </Text>

      <SimpleGrid cols={{ base: 1, sm: 3 }} mb="lg">
        <StatsCard title="Your GPA" value={userGPA != null ? userGPA.toFixed(2) : '-'} />
        <StatsCard title="Saved Combos" value={savedCombos.length} />
        <StatsCard
          title="Unique Majors"
          value={uniqueMajors.length}
        />
      </SimpleGrid>

      {loading && <Loader m="xl" />}

      <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} mb="lg">
        {comboData.map((combo) => {
          const status = gpaStatus(combo.gpaMin, combo.gpaMax)
          const color = UC_COLORS[combo.school] || '#666'
          return (
            <Paper key={combo.id} withBorder p="md" radius="md" style={{ borderLeft: `4px solid ${color}` }}>
              <Group justify="space-between" wrap="nowrap" mb="xs">
                <div>
                  <Text size="sm" fw={600}>{combo.major}</Text>
                  <Text size="xs" c="dimmed">{combo.school}</Text>
                </div>
                <ActionIcon variant="subtle" color="red" size="sm" onClick={() => unsaveCombo(combo.id)}>
                  <IconX size={14} />
                </ActionIcon>
              </Group>

              {!combo.hasData ? (
                <Text size="xs" c="dimmed">No data available</Text>
              ) : (
                <Stack gap={4}>
                  {combo.gpaMin != null ? (
                    <>
                      <Text size="xs" c="dimmed">GPA 25th-75th Percentile ({combo.gpaYear})</Text>
                      <Text size="sm" fw={500}>{combo.gpaMin.toFixed(2)} – {combo.gpaMax.toFixed(2)}</Text>
                    </>
                  ) : (
                    <Text size="xs" c="dimmed">GPA data unavailable</Text>
                  )}
                  {userGPA != null && status && (
                    <Group gap={6}>
                      <Text size="xs">Your GPA: {userGPA.toFixed(2)}</Text>
                      <Badge size="xs" variant="light" color={statusColor[status]}>
                        {statusLabel[status]}
                      </Badge>
                    </Group>
                  )}
                  <Text size="xs" c="dimmed">
                    Avg Admit Rate: {combo.avgRate != null ? `${combo.avgRate}%` : 'N/A'}
                  </Text>
                </Stack>
              )}
            </Paper>
          )
        })}
      </SimpleGrid>

      {chartData.length > 0 && (
        <Stack gap="lg">
          {userGPA != null && (
            <Paper withBorder p="md" radius="md" bg="blue.0">
              <Group gap="lg">
                <div>
                  <Text size="xs" c="dimmed" tt="uppercase" fw={700}>Your GPA</Text>
                  <Text size="lg" fw={700}>{userGPA.toFixed(2)}</Text>
                </div>
                <Divider orientation="vertical" />
                <Text size="sm" c="dimmed">
                  GPA ranges below are per-school, per-major from the most recent year of data.
                </Text>
              </Group>
            </Paper>
          )}

          <div>
            <Title order={4} mb="xs">Admit Rate Trends</Title>
            <TrendChart
              data={chartData}
              xKey="year"
              series={chartSeries}
              colorMap={colorMap}
              yLabel="Avg Admit Rate (%)"
            />
          </div>

          <div>
            <Title order={4} mb="sm">Comparison</Title>
            <Paper withBorder radius="md" style={{ overflow: 'hidden' }}>
              <Table striped highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Major</Table.Th>
                    <Table.Th>School</Table.Th>
                    <Table.Th>Applicants</Table.Th>
                    <Table.Th>Admits</Table.Th>
                    <Table.Th>Avg Admit Rate</Table.Th>
                    <Table.Th>GPA Range 25th-75th Percentile (Latest)</Table.Th>
                    {userGPA != null && <Table.Th>Your GPA</Table.Th>}
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {comboData.filter((c) => c.hasData).map((combo) => {
                    const status = gpaStatus(combo.gpaMin, combo.gpaMax)
                    return (
                      <Table.Tr key={combo.id}>
                        <Table.Td fw={500}>{combo.major}</Table.Td>
                        <Table.Td>{combo.school}</Table.Td>
                        <Table.Td>{combo.totalApps.toLocaleString()}</Table.Td>
                        <Table.Td>{combo.totalAdmits.toLocaleString()}</Table.Td>
                        <Table.Td>{combo.avgRate != null ? `${combo.avgRate}%` : 'N/A'}</Table.Td>
                        <Table.Td>
                          {combo.gpaMin != null
                            ? `${combo.gpaMin.toFixed(2)} – ${combo.gpaMax.toFixed(2)} (${combo.gpaYear})`
                            : 'N/A'}
                        </Table.Td>
                        {userGPA != null && (
                          <Table.Td>
                            {status ? (
                              <Badge size="sm" variant="light" color={statusColor[status]}>
                                {statusLabel[status]}
                              </Badge>
                            ) : '-'}
                          </Table.Td>
                        )}
                      </Table.Tr>
                    )
                  })}
                </Table.Tbody>
              </Table>
            </Paper>
          </div>
        </Stack>
      )}
    </>
  )
}
