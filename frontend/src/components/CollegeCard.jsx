import { useMemo, useState } from 'react'
import { Paper, Text, Select, Group, Button } from '@mantine/core'
import { useCollege } from '../hooks/useUserData'
import { useArticulationColleges } from '../hooks/useApi'

export default function CollegeCard() {
  const { college, setCollege } = useCollege()
  const { data: colleges, loading } = useArticulationColleges()
  const [editing, setEditing] = useState(false)

  const options = useMemo(
    () => (colleges || []).map((c) => ({ value: c.code, label: c.name })),
    [colleges]
  )

  const handleChange = (code) => {
    const match = (colleges || []).find((c) => c.code === code)
    setCollege(match || null)
  }

  return (
    <Paper withBorder p="md" radius="md">
      <Group justify="space-between" mb="sm">
        <Text fw={600}>My Community College</Text>
        <Button
          variant="subtle"
          color="gray"
          size="xs"
          style={{ visibility: college && editing ? 'visible' : 'hidden' }}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => setCollege(null)}
        >
          Clear
        </Button>
      </Group>
      <Select
        placeholder={loading ? 'Loading colleges...' : 'Select your community college'}
        data={options}
        value={college?.code || null}
        onChange={handleChange}
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
