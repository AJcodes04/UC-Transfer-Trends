import { Paper, Text, Group } from '@mantine/core'
import Sparkline from './Sparkline'

export default function StatsCard({
  title, value, subtitle, change, changeUnit = '%', goodDirection = 'up', trend, trendFormat, children,
}) {
  const changeNum = change != null ? parseFloat(change) : null
  const isGood = goodDirection === 'up' ? changeNum > 0 : changeNum < 0
  const color = changeNum === 0 || changeNum == null ? '#868e96' : isGood ? '#2f9e44' : '#e03131'
  const triangle = changeNum > 0 ? '▲' : changeNum < 0 ? '▼' : ''

  return (
    <Paper withBorder p="md" radius="md">
      <Text size="xs" c="dimmed" tt="uppercase" fw={700} mb={4}>
        {title}
      </Text>
      <Text size="xl" fw={700}>
        {value}
      </Text>
      {(changeNum != null || subtitle) && (
        <Group gap={6} mt={4} wrap="nowrap">
          {changeNum != null && (
            <Text size="xs" fw={600} style={{ color, whiteSpace: 'nowrap' }}>
              {triangle} {changeNum > 0 ? '+' : ''}{change}{changeUnit}
            </Text>
          )}
          {subtitle && (
            <Text size="xs" c="dimmed">
              {subtitle}
            </Text>
          )}
        </Group>
      )}
      {trend && <Sparkline data={trend} format={trendFormat} />}
      {children}
    </Paper>
  )
}
