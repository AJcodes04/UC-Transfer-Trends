import { useState } from 'react'
import {
  FileInput, Button, Table, Alert, Loader, Group, Text, Paper, Checkbox, Stack,
} from '@mantine/core'
import axios from 'axios'
import { useCourses } from '../hooks/useUserData'

const API_BASE = import.meta.env.VITE_API_URL || ''

export default function TranscriptUpload() {
  const { addCourses } = useCourses()
  const [file, setFile] = useState(null)
  const [parsed, setParsed] = useState(null)
  const [selected, setSelected] = useState(new Set())
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleUpload = async () => {
    if (!file) return
    setLoading(true)
    setError(null)
    setParsed(null)

    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await axios.post(`${API_BASE}/api/transcript/upload/`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setParsed(res.data)
      setSelected(new Set(res.data.map((_, i) => i)))
    } catch (err) {
      setError(err.response?.data?.error || err.message || 'Upload failed')
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

  const handleConfirm = () => {
    const toAdd = parsed
      .filter((_, i) => selected.has(i))
      .map((c) => ({ ...c, source: 'transcript' }))
    addCourses(toAdd)
    setParsed(null)
    setFile(null)
    setSelected(new Set())
  }

  return (
    <Paper withBorder p="md" radius="md">
      <Text fw={600} mb="sm">Upload Transcript (PDF)</Text>

      <Group align="flex-end" mb="md">
        <FileInput
          label="Select PDF file"
          placeholder="Choose file..."
          accept="application/pdf"
          value={file}
          onChange={setFile}
          style={{ flex: 1 }}
        />
        <Button onClick={handleUpload} disabled={!file} loading={loading}>
          Parse
        </Button>
      </Group>

      {error && <Alert color="red" mb="md">{error}</Alert>}
      {loading && <Loader size="sm" />}

      {parsed && parsed.length > 0 && (
        <Stack gap="sm">
          <Text size="sm" c="dimmed">
            Found {parsed.length} course{parsed.length !== 1 ? 's' : ''}. Review and confirm which to add.
          </Text>

          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>
                  <Checkbox
                    checked={selected.size === parsed.length}
                    indeterminate={selected.size > 0 && selected.size < parsed.length}
                    onChange={toggleAll}
                  />
                </Table.Th>
                <Table.Th>Prefix</Table.Th>
                <Table.Th>Number</Table.Th>
                <Table.Th>Title</Table.Th>
                <Table.Th>Units</Table.Th>
                <Table.Th>Grade</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {parsed.map((course, i) => (
                <Table.Tr key={i}>
                  <Table.Td>
                    <Checkbox checked={selected.has(i)} onChange={() => toggleRow(i)} />
                  </Table.Td>
                  <Table.Td>{course.prefix}</Table.Td>
                  <Table.Td>{course.number}</Table.Td>
                  <Table.Td>{course.title || '-'}</Table.Td>
                  <Table.Td>{course.units}</Table.Td>
                  <Table.Td>{course.grade}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>

          <Group>
            <Button onClick={handleConfirm} disabled={selected.size === 0}>
              Add {selected.size} Course{selected.size !== 1 ? 's' : ''}
            </Button>
            <Button variant="subtle" color="gray" onClick={() => { setParsed(null); setFile(null) }}>
              Cancel
            </Button>
          </Group>
        </Stack>
      )}

      {parsed && parsed.length === 0 && (
        <Alert color="yellow">No courses could be parsed from this PDF.</Alert>
      )}
    </Paper>
  )
}
