import { Table, Group, Badge, Text } from '@mantine/core'
import { SEASON_COLORS } from '../utils/terms'

export default function TermHeaderRow({ group, colSpan }) {
  const units = group.courses.reduce((sum, c) => sum + (parseFloat(c.units) || 0), 0)
  return (
    <Table.Tr bg="var(--mantine-color-gray-0)">
      <Table.Td colSpan={colSpan}>
        <Group gap="sm">
          {group.season ? (
            <Badge color={SEASON_COLORS[group.season]} variant="light" size="sm">{group.season}</Badge>
          ) : (
            <Badge color="gray" variant="light" size="sm">No term</Badge>
          )}
          <Text size="sm" fw={600}>{group.term || 'Unassigned'}</Text>
          <Text size="sm" c="dimmed">
            {group.courses.length} course{group.courses.length !== 1 ? 's' : ''} · {units} unit{units !== 1 ? 's' : ''}
          </Text>
        </Group>
      </Table.Td>
    </Table.Tr>
  )
}
