import { Table, TextInput, NumberInput, Select, Group } from '@mantine/core'
import { SEASONS } from '../utils/terms'
import { GRADE_OPTIONS } from '../utils/grades'

export default function CourseEditCells({ form, onChange }) {
  const set = (field) => (value) => onChange({ ...form, [field]: value })
  return (
    <>
      <Table.Td>
        <Group gap={4} wrap="nowrap">
          <TextInput size="xs" w={90} aria-label="Prefix" value={form.prefix} onChange={(e) => set('prefix')(e.currentTarget.value)} />
          <TextInput size="xs" w={80} aria-label="Number" value={form.number} onChange={(e) => set('number')(e.currentTarget.value)} />
        </Group>
      </Table.Td>
      <Table.Td>
        <TextInput size="xs" aria-label="Title" value={form.title} onChange={(e) => set('title')(e.currentTarget.value)} />
      </Table.Td>
      <Table.Td>
        <NumberInput size="xs" w={80} aria-label="Units" value={form.units} onChange={set('units')} min={0} max={10} step={0.5} />
      </Table.Td>
      <Table.Td>
        <Select size="xs" w={130} aria-label="Grade" data={GRADE_OPTIONS} value={form.grade} onChange={set('grade')} />
      </Table.Td>
      <Table.Td>
        <Group gap={4} wrap="nowrap">
          <Select size="xs" w={110} aria-label="Season" placeholder="Season" data={SEASONS} value={form.season} onChange={set('season')} clearable />
          <NumberInput size="xs" w={80} aria-label="Year" placeholder="Year" value={form.year} onChange={set('year')} min={1990} max={2100} allowDecimal={false} hideControls />
        </Group>
      </Table.Td>
    </>
  )
}
