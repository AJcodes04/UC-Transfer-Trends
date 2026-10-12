import { useMemo } from 'react'
import { Paper, Text, Select, Badge, Group, Button } from '@mantine/core'
import { useCollege } from '../hooks/useUserData'
import { useArticulationColleges } from '../hooks/useApi'

const SOURCE_LABELS = {
  transcript: { label: 'From transcript', color: 'teal' },
  manual: { label: 'Selected manually', color: 'blue' },
}

export default function CollegeCard() {
  const { college, setCollege } = useCollege()
  const { data: colleges, loading } = useArticulationColleges()

  const options = useMemo(
    () => (colleges || []).map((c) => ({ value: c.code, label: c.name })),
    [colleges]
  )

  const handleChange = (code) => {
    const match = (colleges || []).find((c) => c.code === code)
    setCollege(match ? { ...match, source: 'manual' } : null)
  }

  const source = college && SOURCE_LABELS[college.source]

  return (
    <Paper withBorder p="md" radius="md" mb="lg">
      <Group justify="space-between" mb="sm">
        <Group gap="sm">
          <Text fw={600}>My Community College</Text>
          {source && <Badge color={source.color} variant="light">{source.label}</Badge>}
        </Group>
        {college && (
          <Button variant="subtle" color="gray" size="xs" onClick={() => setCollege(null)}>
            Clear
          </Button>
        )}
      </Group>
      <Select
        placeholder={loading ? 'Loading colleges...' : 'Select your community college'}
        data={options}
        value={college?.code || null}
        onChange={handleChange}
        searchable
        clearable
        disabled={loading}
        maw={400}
      />
      <Text size="xs" c="dimmed" mt="xs">
        Used to preselect your college on the Transfer Requirements page. Uploading a transcript fills this in automatically.
      </Text>
    </Paper>
  )
}
