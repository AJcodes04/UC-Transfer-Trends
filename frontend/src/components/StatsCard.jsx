import { Paper, Text, Group } from '@mantine/core'

export default function StatsCard({ title, value, subtitle, change }) {
  const changeNum = change != null ? parseFloat(change) : null
  const color = changeNum > 0 ? '#2f9e44' : changeNum < 0 ? '#e03131' : '#868e96'
  const triangle = changeNum > 0 ? '▲' : changeNum < 0 ? '▼' : ''

  return (
    <Paper withBorder p="md" radius="md">
      <Group justify="space-between" align="center" mb={4}>
        <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
          {title}
        </Text>
        {changeNum != null && (
          <Text size="xs" fw={600} style={{ color }}>
            {triangle} {changeNum > 0 ? '+' : ''}{change}%
          </Text>
        )}
      </Group>
      <Text size="xl" fw={700}>
        {value}
      </Text>
      {subtitle && (
        <Text size="xs" c="dimmed" mt={4}>
          {subtitle}
        </Text>
      )}
    </Paper>
  )
}
