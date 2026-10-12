import { useMemo } from 'react'
import { Select } from '@mantine/core'
import { useMajor } from '../hooks/useUserData'
import { useGroupedMajors } from '../hooks/useApi'

export default function MajorSelect(props) {
  const { major, setMajor } = useMajor()
  const { data: groups, loading } = useGroupedMajors()

  const options = useMemo(() => {
    const names = new Set()
    for (const group of groups || []) {
      names.add(group.name)
      for (const related of group.related || []) names.add(related.name)
    }
    return [...names].sort((a, b) => a.localeCompare(b))
  }, [groups])

  return (
    <Select
      label="Major"
      placeholder={loading ? 'Loading majors...' : 'Select your major'}
      data={options}
      value={major || null}
      onChange={setMajor}
      searchable
      clearable
      disabled={loading}
      {...props}
    />
  )
}
