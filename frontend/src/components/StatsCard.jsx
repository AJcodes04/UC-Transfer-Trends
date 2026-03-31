import { Paper, Text, Group, Badge } from '@mantine/core'

export default function StatsCard({ title, value, subtitle, change }) {
  return (
    <Paper withBorder p="md" radius="md">
      <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
        {title}
      </Text>
      <Group justify="space-between" align="flex-end" mt={4}>
        <Text size="xl" fw={700}>
          {value}
        </Text>
        {change != null && (
          <Badge
            size="lg"
            variant="light"
            color={change > 0 ? 'green' : change < 0 ? 'red' : 'gray'}
          >
            {change > 0 ? '+' : ''}{change}%
          </Badge>
        )}
      </Group>
      {subtitle && (
        <Text size="xs" c="dimmed" mt={4}>
          {subtitle}
        </Text>
      )}
    </Paper>
  )
}
