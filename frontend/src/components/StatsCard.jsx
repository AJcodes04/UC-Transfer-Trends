import { Paper, Text, Group } from '@mantine/core'

/**
 * Reusable stat card — shows a title, large value, and optional subtitle.
 */
export default function StatsCard({ title, value, subtitle }) {
  return (
    <Paper withBorder p="md" radius="md">
      <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
        {title}
      </Text>
      <Text size="xl" fw={700} mt={4}>
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
