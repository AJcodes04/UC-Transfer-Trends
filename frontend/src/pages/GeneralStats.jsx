import { useState, useMemo, useEffect } from 'react'
import { Title, SimpleGrid, Table, Loader, Alert, Slider, Text, Group } from '@mantine/core'
import { useGeneralStats } from '../hooks/useApi'
import StatsCard from '../components/StatsCard'
import TrendChart from '../components/TrendChart'
import { UC_COLORS } from '../utils/ucColors'
import { computeCardStats, formatDelta } from '../utils/cardStats'

const Y_AXIS_OPTIONS = [
  { value: 'admitRate', label: 'Admit Rate (%)' },
  { value: 'gpa', label: 'Lowest GPA (25th percentile)' },
]

export default function GeneralStats() {
  const { data: stats, loading, error } = useGeneralStats()
  const [yAxis, setYAxis] = useState('admitRate')
  const [selectedYear, setSelectedYear] = useState(null)
  const [selectedUCs, setSelectedUCs] = useState([])

  const allUCs = useMemo(() => {
    if (!stats) return []
    return [...new Set(stats.map((s) => s.campus))].sort()
  }, [stats])

  const activeUCs = selectedUCs.length > 0 ? selectedUCs : allUCs
  const activeStats = useMemo(
    () => (stats || []).filter((r) => activeUCs.includes(r.campus)),
    [stats, activeUCs],
  )

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

  const cardYear = selectedYear || (availableYears.length ? availableYears[availableYears.length - 1] : null)
  const prevCardYear = cardYear ? cardYear - 1 : null

  const cards = useMemo(() => computeCardStats(
    activeStats.map((r) => ({
      year: r.year, applicants: r.applicants, admits: r.admits, enrolls: r.enrolls,
      gpaMin: r.admit_gpa_min != null ? parseFloat(r.admit_gpa_min) : null,
    })),
    cardYear,
  ), [activeStats, cardYear])

  const mostCompetitive = useMemo(() => {
    if (!stats || !cardYear) return { current: null, prev: null }
    const forYear = (y) => {
      const rows = activeStats.filter((r) => r.year === y && r.admit_rate != null)
      if (!rows.length) return null
      return rows.reduce((best, r) => (!best || r.admit_rate < best.admit_rate ? r : best), null)
    }
    return { current: forYear(cardYear), prev: forYear(prevCardYear) }
  }, [stats, activeStats, cardYear, prevCardYear])

  const pct = (v) => `${v.toFixed(1)}%`
  const gpa = (v) => v.toFixed(2)
  const perSeat = (v) => `${v.toFixed(1)}:1`

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
        selectedKeys={selectedUCs}
        onSelectedKeysChange={setSelectedUCs}
      />

      {cards && (
        <SimpleGrid cols={{ base: 1, sm: 2, md: 3, lg: 5 }} mt="lg" mb="lg">
          <StatsCard
            title={`Admit rate (${cardYear})`}
            value={cards.admitRate.value != null ? pct(cards.admitRate.value) : 'N/A'}
            change={formatDelta(cards.admitRate.delta)}
            changeUnit=" pt"
            subtitle={`vs ${prevCardYear}`}
            trend={cards.admitRate.series}
            trendFormat={pct}
          />
          <StatsCard
            title={`${cards.lookback}-year trend`}
            value={cards.direction || 'N/A'}
            change={formatDelta(cards.admitRate.lookbackDelta)}
            changeUnit=" pt"
            subtitle={`Admit rate since ${cardYear - cards.lookback}`}
          />
          <StatsCard
            title={`GPA floor (${cardYear})`}
            value={cards.gpaFloor.value != null ? gpa(cards.gpaFloor.value) : 'N/A'}
            change={formatDelta(cards.gpaFloor.lookbackDelta, 2)}
            changeUnit=""
            goodDirection="down"
            subtitle={`25th percentile, vs ${cardYear - cards.lookback}`}
            trend={cards.gpaFloor.series}
            trendFormat={gpa}
          />
          <StatsCard
            title={`Applicants per seat (${cardYear})`}
            value={cards.perSeat.value != null ? perSeat(cards.perSeat.value) : 'N/A'}
            change={formatDelta(cards.perSeat.delta)}
            changeUnit=""
            goodDirection="down"
            subtitle={`vs ${prevCardYear}`}
            trend={cards.perSeat.series}
            trendFormat={perSeat}
          />
          <StatsCard
            title={`Most competitive (${cardYear})`}
            value={mostCompetitive.current ? mostCompetitive.current.campus : '-'}
            change={mostCompetitive.current && mostCompetitive.prev
              ? formatDelta(mostCompetitive.current.admit_rate - mostCompetitive.prev.admit_rate, 0)
              : null}
            changeUnit=" pt"
            subtitle={mostCompetitive.current ? `${mostCompetitive.current.admit_rate}% admit rate` : undefined}
          />
        </SimpleGrid>
      )}

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
