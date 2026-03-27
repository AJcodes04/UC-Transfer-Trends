import { Group, MultiSelect, Select } from '@mantine/core'

export default function FilterBar({ filters = [] }) {
  return (
    <Group mb="md">
      {filters.map((f, i) => {
        const Component = f.type === 'multiselect' ? MultiSelect : Select
        return (
          <Component
            key={i}
            label={f.label}
            data={f.data || []}
            value={f.value}
            onChange={f.onChange}
            searchable={f.searchable ?? true}
            clearable={f.clearable ?? true}
            placeholder={f.placeholder || `Select ${f.label}`}
            style={{ minWidth: 220 }}
          />
        )
      })}
    </Group>
  )
}
