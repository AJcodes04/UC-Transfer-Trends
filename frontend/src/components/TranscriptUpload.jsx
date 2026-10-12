import { useState, Fragment } from 'react'
import { Button, Table, Alert, Group, Text, Checkbox, Stack, Badge, ActionIcon } from '@mantine/core'
import { IconEdit, IconCheck, IconX } from '@tabler/icons-react'
import axios from 'axios'
import { useCollege, useCourses } from '../hooks/useUserData'
import { groupByTerm, toEditForm, fromEditForm } from '../utils/terms'
import FileDropzone from './FileDropzone'
import TermHeaderRow from './TermHeaderRow'
import CourseEditCells from './CourseEditCells'

const API_BASE = import.meta.env.VITE_API_URL || ''

export default function TranscriptUpload() {
  const { addCourses } = useCourses()
  const { setCollege } = useCollege()
  const [file, setFile] = useState(null)
  const [parsed, setParsed] = useState(null)
  const [detected, setDetected] = useState(null)
  const [selected, setSelected] = useState(new Set())
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [remaining, setRemaining] = useState(null)
  const [editingIndex, setEditingIndex] = useState(null)
  const [form, setForm] = useState({})

  const handleFile = async (picked) => {
    setFile(picked)
    setLoading(true)
    setError(null)
    setParsed(null)

    try {
      const formData = new FormData()
      formData.append('file', picked)
      const res = await axios.post(`${API_BASE}/api/transcript/upload/`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setParsed(res.data.courses)
      setDetected(res.data.college)
      setSelected(new Set(res.data.courses.flatMap((c, i) => (c.needs_review ? [] : [i]))))
      const rem = res.headers.get
        ? res.headers.get('x-ratelimit-remaining')
        : res.headers['x-ratelimit-remaining']
      if (rem != null) setRemaining(parseInt(rem, 10))
    } catch (err) {
      const msg = err.response?.data?.error || err.message || 'Upload failed'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const toggleRow = (index) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(index)) next.delete(index)
      else next.add(index)
      return next
    })
  }

  const toggleAll = () => {
    if (selected.size === parsed.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(parsed.map((_, i) => i)))
    }
  }

  const reviewCount = parsed ? parsed.filter((c) => c.needs_review).length : 0

  const saveEdit = () => {
    setParsed((prev) => prev.map((c, i) => (i === editingIndex ? { ...c, ...fromEditForm(form), needs_review: false } : c)))
    setSelected((prev) => new Set(prev).add(editingIndex))
    setEditingIndex(null)
  }

  const reset = () => {
    setParsed(null)
    setFile(null)
    setSelected(new Set())
    setEditingIndex(null)
  }

  const groups = parsed ? groupByTerm(parsed.map((c, i) => ({ ...c, i }))) : []

  const handleConfirm = () => {
    const toAdd = parsed
      .filter((_, i) => selected.has(i))
      .map(({ prefix, number, title, units, grade, term }) => ({ prefix, number, title, units, grade, term: term || '', source: 'transcript' }))
    addCourses(toAdd)
    if (detected) setCollege(detected)
    reset()
  }

  return (
    <Stack gap="sm">
      <FileDropzone
        onFile={handleFile}
        loading={loading}
        fileName={file?.name}
        hint={file ? 'Drop another PDF or click to replace it' : undefined}
      />

      {remaining != null && (
        <Text size="xs" c="dimmed">
          {remaining} parse{remaining !== 1 ? 's' : ''} remaining today
        </Text>
      )}

      {error && <Alert color="red">{error}</Alert>}

      {parsed && parsed.length > 0 && (
        <Stack gap="sm">
          <Text size="sm" c="dimmed">
            Found {parsed.length} course{parsed.length !== 1 ? 's' : ''}
            {detected ? ` from ${detected.name}` : ''}. Review and confirm which to add.
          </Text>
          {reviewCount > 0 && (
            <Alert color="yellow" py="xs">
              {reviewCount} course{reviewCount !== 1 ? 's were' : ' was'} hard to read and {reviewCount !== 1 ? 'are' : 'is'} unchecked. Check the details before adding.
            </Alert>
          )}

          <Table.ScrollContainer minWidth={700}>
            <Table highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>
                    <Checkbox
                      aria-label="Select all parsed courses"
                      checked={selected.size === parsed.length}
                      indeterminate={selected.size > 0 && selected.size < parsed.length}
                      onChange={toggleAll}
                    />
                  </Table.Th>
                  <Table.Th>Course</Table.Th>
                  <Table.Th>Title</Table.Th>
                  <Table.Th>Units</Table.Th>
                  <Table.Th>Grade</Table.Th>
                  <Table.Th />
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {groups.map((group) => (
                  <Fragment key={group.term || 'unassigned'}>
                    <TermHeaderRow group={group} colSpan={7} />
                    {group.courses.map((course) => {
                      const i = course.i
                      return (
                        <Table.Tr key={i} bg={course.needs_review ? 'var(--mantine-color-yellow-light)' : undefined}>
                          <Table.Td>
                            <Checkbox
                              aria-label={`Add ${course.prefix} ${course.number}`}
                              checked={selected.has(i)}
                              onChange={() => toggleRow(i)}
                            />
                          </Table.Td>
                          {editingIndex === i ? (
                            <>
                              <CourseEditCells form={form} onChange={setForm} />
                              <Table.Td>
                                <Group gap={4} wrap="nowrap">
                                  <ActionIcon size="sm" color="green" variant="subtle" aria-label="Save changes" onClick={saveEdit}>
                                    <IconCheck size={14} />
                                  </ActionIcon>
                                  <ActionIcon size="sm" color="gray" variant="subtle" aria-label="Cancel editing" onClick={() => setEditingIndex(null)}>
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
                                {course.needs_review && <Badge color="yellow" variant="light">Check</Badge>}
                              </Table.Td>
                              <Table.Td>
                                <ActionIcon
                                  size="sm" variant="subtle" aria-label={`Edit ${course.prefix} ${course.number}`}
                                  onClick={() => { setEditingIndex(i); setForm(toEditForm(course)) }}
                                >
                                  <IconEdit size={14} />
                                </ActionIcon>
                              </Table.Td>
                            </>
                          )}
                        </Table.Tr>
                      )
                    })}
                  </Fragment>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>

          <Group>
            <Button onClick={handleConfirm} disabled={selected.size === 0 || editingIndex !== null}>
              Add {selected.size} course{selected.size !== 1 ? 's' : ''}
            </Button>
            <Button variant="subtle" color="gray" onClick={reset}>
              Cancel
            </Button>
          </Group>
        </Stack>
      )}

      {parsed && parsed.length === 0 && (
        <Alert color="yellow">No courses could be parsed from this PDF.</Alert>
      )}
    </Stack>
  )
}
