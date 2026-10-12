import { useState, Fragment } from 'react'
import { Table, Group, ActionIcon, Badge } from '@mantine/core'
import { IconTrash, IconEdit, IconCheck, IconX } from '@tabler/icons-react'
import { groupByTerm, toEditForm, fromEditForm } from '../utils/terms'
import TermHeaderRow from './TermHeaderRow'
import CourseEditCells from './CourseEditCells'

const SOURCE_LABELS = { manual: 'Manual', transcript: 'Transcript' }

export default function CourseHistoryTable({ courses, onUpdate, onRemove }) {
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState({})

  const startEdit = (course) => {
    setEditingId(course.id)
    setForm(toEditForm(course))
  }

  const saveEdit = () => {
    onUpdate(editingId, fromEditForm(form))
    setEditingId(null)
  }

  const renderRow = (course) => (
    <Table.Tr key={course.id}>
      {editingId === course.id ? (
        <>
          <CourseEditCells form={form} onChange={setForm} />
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
  )

  return (
    <Table.ScrollContainer minWidth={640}>
      <Table highlightOnHover>
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
          {groupByTerm(courses).map((group) => (
            <Fragment key={group.term || 'unassigned'}>
              <TermHeaderRow group={group} colSpan={6} />
              {group.courses.map(renderRow)}
            </Fragment>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  )
}
