import { useState } from 'react'
import {
  Title, Text, SimpleGrid, Table, TextInput, NumberInput, Select, Button,
  Group, ActionIcon, Paper, Modal, Stack,
} from '@mantine/core'
import { IconTrash, IconEdit, IconCheck, IconX } from '@tabler/icons-react'
import StatsCard from '../components/StatsCard'
import TranscriptUpload from '../components/TranscriptUpload'
import { useCourses, useGPA } from '../hooks/useUserData'

const GRADE_OPTIONS = [
  'A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-',
  'D+', 'D', 'D-', 'F', 'P', 'NP',
]

export default function MyCourses() {
  const { courses, addCourse, removeCourse, updateCourse, clearCourses } = useCourses()
  const gpa = useGPA()

  const [prefix, setPrefix] = useState('')
  const [number, setNumber] = useState('')
  const [title, setTitle] = useState('')
  const [units, setUnits] = useState(3)
  const [grade, setGrade] = useState(null)

  const [editingId, setEditingId] = useState(null)
  const [editForm, setEditForm] = useState({})

  const [clearOpen, setClearOpen] = useState(false)

  const handleAdd = () => {
    if (!prefix.trim() || !number.trim() || !grade) return
    addCourse({
      prefix: prefix.trim().toUpperCase(),
      number: number.trim(),
      title: title.trim(),
      units: units || 0,
      grade,
      source: 'manual',
    })
    setPrefix('')
    setNumber('')
    setTitle('')
    setUnits(3)
    setGrade(null)
  }

  const startEdit = (course) => {
    setEditingId(course.id)
    setEditForm({
      prefix: course.prefix,
      number: course.number,
      title: course.title || '',
      units: course.units,
      grade: course.grade,
    })
  }

  const saveEdit = () => {
    updateCourse(editingId, {
      prefix: editForm.prefix.trim().toUpperCase(),
      number: editForm.number.trim(),
      title: editForm.title.trim(),
      units: editForm.units,
      grade: editForm.grade,
    })
    setEditingId(null)
  }

  return (
    <>
      <Title order={2} mb="md">My Courses</Title>
      <Text c="dimmed" size="sm" mb="lg">
        Track your completed courses for transfer planning. Add manually or upload a transcript.
      </Text>

      <SimpleGrid cols={{ base: 1, sm: 3 }} mb="lg">
        <StatsCard title="Overall GPA" value={gpa != null ? gpa.toFixed(2) : '-'} />
        <StatsCard title="Total Courses" value={courses.length} />
        <StatsCard
          title="Total Units"
          value={courses.reduce((sum, c) => sum + (parseFloat(c.units) || 0), 0).toFixed(1)}
        />
      </SimpleGrid>

      <Paper withBorder p="md" radius="md" mb="lg">
        <Text fw={600} mb="sm">Add Course</Text>
        <Group align="flex-end" grow>
          <TextInput
            label="Prefix"
            placeholder="e.g. MATH"
            value={prefix}
            onChange={(e) => setPrefix(e.currentTarget.value)}
            required
          />
          <TextInput
            label="Number"
            placeholder="e.g. 101"
            value={number}
            onChange={(e) => setNumber(e.currentTarget.value)}
            required
          />
          <TextInput
            label="Title"
            placeholder="(optional)"
            value={title}
            onChange={(e) => setTitle(e.currentTarget.value)}
          />
          <NumberInput
            label="Units"
            value={units}
            onChange={setUnits}
            min={0}
            max={10}
            step={0.5}
            required
          />
          <Select
            label="Grade"
            placeholder="Select"
            data={GRADE_OPTIONS}
            value={grade}
            onChange={setGrade}
            required
          />
          <Button onClick={handleAdd} disabled={!prefix.trim() || !number.trim() || !grade}>
            Add
          </Button>
        </Group>
      </Paper>

      <div style={{ marginBottom: '1.5rem' }}>
        <TranscriptUpload />
      </div>

      {courses.length > 0 && (
        <>
          <Group justify="space-between" mb="sm">
            <Title order={4}>Course List</Title>
            <Button variant="subtle" color="red" size="xs" onClick={() => setClearOpen(true)}>
              Clear All
            </Button>
          </Group>

          <Paper withBorder radius="md" style={{ overflow: 'hidden' }}>
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Prefix</Table.Th>
                  <Table.Th>Number</Table.Th>
                  <Table.Th>Title</Table.Th>
                  <Table.Th>Units</Table.Th>
                  <Table.Th>Grade</Table.Th>
                  <Table.Th>Source</Table.Th>
                  <Table.Th></Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {courses.map((course) => (
                  <Table.Tr key={course.id}>
                    {editingId === course.id ? (
                      <>
                        <Table.Td>
                          <TextInput
                            size="xs" value={editForm.prefix}
                            onChange={(e) => setEditForm({ ...editForm, prefix: e.currentTarget.value })}
                          />
                        </Table.Td>
                        <Table.Td>
                          <TextInput
                            size="xs" value={editForm.number}
                            onChange={(e) => setEditForm({ ...editForm, number: e.currentTarget.value })}
                          />
                        </Table.Td>
                        <Table.Td>
                          <TextInput
                            size="xs" value={editForm.title}
                            onChange={(e) => setEditForm({ ...editForm, title: e.currentTarget.value })}
                          />
                        </Table.Td>
                        <Table.Td>
                          <NumberInput size="xs" value={editForm.units} onChange={(v) => setEditForm({ ...editForm, units: v })} />
                        </Table.Td>
                        <Table.Td>
                          <Select size="xs" data={GRADE_OPTIONS} value={editForm.grade} onChange={(v) => setEditForm({ ...editForm, grade: v })} />
                        </Table.Td>
                        <Table.Td>{course.source || '-'}</Table.Td>
                        <Table.Td>
                          <Group gap={4}>
                            <ActionIcon size="sm" color="green" variant="subtle" onClick={saveEdit}>
                              <IconCheck size={14} />
                            </ActionIcon>
                            <ActionIcon size="sm" color="gray" variant="subtle" onClick={() => setEditingId(null)}>
                              <IconX size={14} />
                            </ActionIcon>
                          </Group>
                        </Table.Td>
                      </>
                    ) : (
                      <>
                        <Table.Td>{course.prefix}</Table.Td>
                        <Table.Td>{course.number}</Table.Td>
                        <Table.Td>{course.title || '-'}</Table.Td>
                        <Table.Td>{course.units}</Table.Td>
                        <Table.Td>{course.grade}</Table.Td>
                        <Table.Td>{course.source || '-'}</Table.Td>
                        <Table.Td>
                          <Group gap={4}>
                            <ActionIcon size="sm" variant="subtle" onClick={() => startEdit(course)}>
                              <IconEdit size={14} />
                            </ActionIcon>
                            <ActionIcon size="sm" color="red" variant="subtle" onClick={() => removeCourse(course.id)}>
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
          </Paper>
        </>
      )}

      {courses.length === 0 && (
        <Text c="dimmed" ta="center" mt="xl">
          No courses added yet. Use the form above or upload a transcript to get started.
        </Text>
      )}

      <Modal opened={clearOpen} onClose={() => setClearOpen(false)} title="Clear All Courses?" centered>
        <Stack>
          <Text size="sm">This will remove all {courses.length} courses. This cannot be undone.</Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setClearOpen(false)}>Cancel</Button>
            <Button color="red" onClick={() => { clearCourses(); setClearOpen(false) }}>Clear All</Button>
          </Group>
        </Stack>
      </Modal>
    </>
  )
}
