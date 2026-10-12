import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
} from 'recharts'
import { Group, Text, Paper, Stack } from '@mantine/core'

const SERIES = [
  { key: 'cumulativeGPA', label: 'Cumulative GPA', color: 'var(--mantine-color-uc-blue-6)' },
  { key: 'termGPA', label: 'Term GPA', color: 'var(--mantine-color-orange-8)' },
]

function LineKey({ color, dashed }) {
  return (
    <svg width={18} height={8} aria-hidden="true">
      <line x1={0} y1={4} x2={18} y2={4} stroke={color} strokeWidth={2} strokeDasharray={dashed ? '4 3' : undefined} />
    </svg>
  )
}

function TrendTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload
  return (
    <Paper withBorder shadow="sm" radius="md" p="sm" style={{ pointerEvents: 'none' }}>
      <Text size="sm" fw={600} mb={4}>{point.term}</Text>
      <Stack gap={2}>
        {SERIES.map((s) => (
          <Group key={s.key} gap="xs" wrap="nowrap">
            <LineKey color={s.color} dashed={s.key === 'termGPA'} />
            <Text size="sm" fw={600}>{point[s.key] != null ? point[s.key].toFixed(2) : '—'}</Text>
            <Text size="sm" c="dimmed">{s.label}</Text>
          </Group>
        ))}
        <Text size="xs" c="dimmed" mt={2}>
          {point.termUnits} unit{point.termUnits !== 1 ? 's' : ''} this term · {point.cumulativeUnits} total
        </Text>
      </Stack>
    </Paper>
  )
}

export default function GpaTrendChart({ data }) {
  const values = data.flatMap((d) => [d.termGPA, d.cumulativeGPA]).filter((v) => v != null)
  const floor = Math.max(0, Math.floor((Math.min(...values) - 0.25) * 2) / 2)

  return (
    <div>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ top: 12, right: 24, bottom: 4, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--mantine-color-gray-2)" />
          <XAxis
            dataKey="term"
            tickLine={false}
            axisLine={{ stroke: 'var(--mantine-color-gray-3)' }}
            tick={{ fill: 'var(--mantine-color-dimmed)', fontSize: 12 }}
          />
          <YAxis
            domain={[floor, 4]}
            ticks={[...Array(Math.round((4 - floor) * 2) + 1)].map((_, i) => floor + i * 0.5)}
            tickLine={false}
            axisLine={false}
            width={36}
            tick={{ fill: 'var(--mantine-color-dimmed)', fontSize: 12 }}
            tickFormatter={(v) => v.toFixed(1)}
          />
          <Tooltip
            content={<TrendTooltip />}
            cursor={{ stroke: 'var(--mantine-color-gray-4)', strokeDasharray: '3 3' }}
            wrapperStyle={{ zIndex: 10, outline: 'none' }}
          />
          <Line
            type="monotone" dataKey="termGPA" name="Term GPA"
            stroke={SERIES[1].color} strokeWidth={2} strokeDasharray="4 3"
            dot={{ r: 4, strokeWidth: 2, fill: 'var(--mantine-color-body)' }}
            activeDot={{ r: 6 }} connectNulls isAnimationActive={false}
          />
          <Line
            type="monotone" dataKey="cumulativeGPA" name="Cumulative GPA"
            stroke={SERIES[0].color} strokeWidth={2}
            dot={{ r: 4, strokeWidth: 2, fill: 'var(--mantine-color-body)' }}
            activeDot={{ r: 6 }} connectNulls isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
      <Group justify="center" gap="lg" mt={4}>
        {SERIES.map((s) => (
          <Group key={s.key} gap={6} wrap="nowrap">
            <LineKey color={s.color} dashed={s.key === 'termGPA'} />
            <Text size="xs" c="dimmed">{s.label}</Text>
          </Group>
        ))}
      </Group>
    </div>
  )
}
