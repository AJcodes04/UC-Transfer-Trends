import { useMemo, useState } from 'react'
import { Paper, Text, Select, Group, Button } from '@mantine/core'
import { useMajor } from '../hooks/useUserData'
import { useGroupedMajors } from '../hooks/useApi'

export default function MajorCard() {
  const { major, setMajor } = useMajor()
  const { data: groups, loading } = useGroupedMajors()
  const [editing, setEditing] = useState(false)

  const options = useMemo(() => {
    const names = new Set()
    for (const group of groups || []) {
      names.add(group.name)
      for (const related of group.related || []) names.add(related.name)
    }
    return [...names].sort((a, b) => a.localeCompare(b))
  }, [groups])

  return (
    <Paper withBorder p="md" radius="md">
      <Group justify="space-between" mb="sm">
        <Text fw={600}>My Major</Text>
        <Button
          variant="subtle"
          color="gray"
          size="xs"
          style={{ visibility: major && editing ? 'visible' : 'hidden' }}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => setMajor(null)}
        >
          Clear
        </Button>
      </Group>
      <Select
        placeholder={loading ? 'Loading majors...' : 'Select your intended major'}
        data={options}
        value={major || null}
        onChange={setMajor}
        onFocus={() => setEditing(true)}
        onBlur={() => setEditing(false)}
        searchable
        clearable
        disabled={loading}
        maw={400}
      />
    </Paper>
  )
}
