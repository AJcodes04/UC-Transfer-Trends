import { useMemo } from 'react'
import { Select } from '@mantine/core'
import { useCollege } from '../hooks/useUserData'
import { useArticulationColleges } from '../hooks/useApi'

export default function CollegeSelect(props) {
  const { college, setCollege } = useCollege()
  const { data: colleges, loading } = useArticulationColleges()

  const options = useMemo(
    () => (colleges || []).map((c) => ({ value: c.code, label: c.name })),
    [colleges]
  )

  const handleChange = (code) => {
    const match = (colleges || []).find((c) => c.code === code)
    setCollege(match || null)
  }

  return (
    <Select
      label="Community college"
      placeholder={loading ? 'Loading colleges...' : 'Select your college'}
      data={options}
      value={college?.code || null}
      onChange={handleChange}
      searchable
      clearable
      disabled={loading}
      {...props}
    />
  )
}
