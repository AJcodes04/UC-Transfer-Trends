import { useState } from 'react'
import { Table, TextInput, NumberInput, Select, Group, ActionIcon, Badge } from '@mantine/core'
import { IconTrash, IconEdit, IconCheck, IconX } from '@tabler/icons-react'

const SOURCE_LABELS = { manual: 'Manual', transcript: 'Transcript' }

export default function CourseHistoryTable({ courses, gradeOptions, onUpdate, onRemove }) {
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState({})

  const startEdit = (course) => {
    setEditingId(course.id)
    setForm({
      prefix: course.prefix,
      number: course.number,
      title: course.title || '',
      units: course.units,
      grade: course.grade,
    })
  }

  const saveEdit = () => {
    onUpdate(editingId, {
      prefix: form.prefix.trim().toUpperCase(),
      number: form.number.trim(),
      title: form.title.trim(),
      units: form.units,
      grade: form.grade,
    })
    setEditingId(null)
  }

  const set = (field) => (value) => setForm((f) => ({ ...f, [field]: value }))

  return (
    <Table.ScrollContainer minWidth={640}>
      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Course</Table.Th>
            <Table.Th>Title</Table.Th>
            <Table.Th>Units</Table.Th>
            <Table.Th>Grade</Table.Th>
            <Table.Th>Source</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {courses.map((course) => (
            <Table.Tr key={course.id}>
              {editingId === course.id ? (
                <>
                  <Table.Td>
                    <Group gap={4} wrap="nowrap">
                      <TextInput
                        size="xs" w={90} aria-label="Prefix" value={form.prefix}
                        onChange={(e) => set('prefix')(e.currentTarget.value)}
                      />
                      <TextInput
                        size="xs" w={80} aria-label="Number" value={form.number}
                        onChange={(e) => set('number')(e.currentTarget.value)}
                      />
                    </Group>
                  </Table.Td>
                  <Table.Td>
                    <TextInput
                      size="xs" aria-label="Title" value={form.title}
                      onChange={(e) => set('title')(e.currentTarget.value)}
                    />
                  </Table.Td>
                  <Table.Td>
                    <NumberInput size="xs" w={80} aria-label="Units" value={form.units} onChange={set('units')} min={0} max={10} step={0.5} />
                  </Table.Td>
                  <Table.Td>
                    <Select size="xs" w={130} aria-label="Grade" data={gradeOptions} value={form.grade} onChange={set('grade')} />
                  </Table.Td>
                  <Table.Td>{SOURCE_LABELS[course.source] || '-'}</Table.Td>
                  <Table.Td>
                    <Group gap={4} wrap="nowrap">
                      <ActionIcon size="sm" color="green" variant="subtle" aria-label="Save changes" onClick={saveEdit}>
                        <IconCheck size={14} />
                      </ActionIcon>
                      <ActionIcon size="sm" color="gray" variant="subtle" aria-label="Cancel editing" onClick={() => setEditingId(null)}>
                        <IconX size={14} />
                      </ActionIcon>
                    </Group>
                  </Table.Td>
                </>
              ) : (
                <>
                  <Table.Td fw={600} style={{ whiteSpace: 'nowrap' }}>{course.prefix} {course.number}</Table.Td>
                  <Table.Td>{course.title || '-'}</Table.Td>
                  <Table.Td>{course.units}</Table.Td>
                  <Table.Td>{course.grade === 'IP' ? 'In progress' : course.grade}</Table.Td>
                  <Table.Td>
                    {course.source ? (
                      <Badge size="sm" variant="light" color="gray">{SOURCE_LABELS[course.source] || course.source}</Badge>
                    ) : '-'}
                  </Table.Td>
                  <Table.Td>
                    <Group gap={4} wrap="nowrap">
                      <ActionIcon size="sm" variant="subtle" aria-label={`Edit ${course.prefix} ${course.number}`} onClick={() => startEdit(course)}>
                        <IconEdit size={14} />
                      </ActionIcon>
                      <ActionIcon size="sm" color="red" variant="subtle" aria-label={`Remove ${course.prefix} ${course.number}`} onClick={() => onRemove(course.id)}>
                        <IconTrash size={14} />
                      </ActionIcon>
                    </Group>
                  </Table.Td>
                </>
              )}
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  )
}
