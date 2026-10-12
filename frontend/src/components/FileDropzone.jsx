import { useRef, useState } from 'react'
import { Paper, Stack, Text, ThemeIcon, Loader } from '@mantine/core'
import { IconUpload } from '@tabler/icons-react'

export default function FileDropzone({ onFile, accept = 'application/pdf', loading = false, fileName, hint }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)

  const open = () => { if (!loading) inputRef.current?.click() }

  const handleFiles = (files) => {
    const file = files?.[0]
    if (file) onFile(file)
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open() }
  }

  const onDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    if (!loading) handleFiles(e.dataTransfer.files)
  }

  return (
    <Paper
      role="button"
      tabIndex={0}
      aria-label="Upload transcript PDF"
      aria-busy={loading}
      withBorder
      radius="md"
      p="xl"
      onClick={open}
      onKeyDown={onKeyDown}
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      style={{
        cursor: loading ? 'default' : 'pointer',
        borderStyle: 'dashed',
        borderWidth: 2,
        borderColor: dragging ? 'var(--mantine-primary-color-filled)' : 'var(--mantine-color-default-border)',
        backgroundColor: dragging ? 'var(--mantine-primary-color-light)' : 'var(--mantine-color-body)',
        transition: 'border-color 120ms ease, background-color 120ms ease',
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        hidden
        onChange={(e) => { handleFiles(e.target.files); e.target.value = '' }}
      />
      <Stack align="center" gap="xs">
        {loading ? (
          <Loader size="md" />
        ) : (
          <ThemeIcon variant="light" size="xl" radius="xl">
            <IconUpload size={22} />
          </ThemeIcon>
        )}
        <Text fw={600} ta="center">
          {loading ? 'Reading your transcript...' : fileName || 'Drop your transcript PDF here'}
        </Text>
        <Text size="sm" c="dimmed" ta="center">
          {loading ? 'This can take a few seconds.' : hint || 'or click to choose a file'}
        </Text>
      </Stack>
    </Paper>
  )
}
