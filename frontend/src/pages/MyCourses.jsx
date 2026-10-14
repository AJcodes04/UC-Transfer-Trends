import { useMemo, useState } from 'react'
import {
  Title, Text, SimpleGrid, TextInput, NumberInput, Select, Button,
  Group, Paper, Modal, Stack, SegmentedControl, Box,
} from '@mantine/core'
import { useReducedMotion } from '@mantine/hooks'
import StatsCard from '../components/StatsCard'
import CountUp from '../components/CountUp'
import TransferUnitsCard from '../components/TransferUnitsCard'
import TranscriptUpload from '../components/TranscriptUpload'
import CollegeSelect from '../components/CollegeSelect'
import MajorSelect from '../components/MajorSelect'
import CourseHistoryTable from '../components/CourseHistoryTable'
import GpaTrendChart from '../components/GpaTrendChart'
import { useCourses, useGPA } from '../hooks/useUserData'
import { SEASONS, formatTerm, termTrend } from '../utils/terms'
import { GRADE_OPTIONS, NON_TRANSFERABLE, NOT_COMPLETED } from '../utils/grades'

const TRANSFER_UNIT_TARGET = 60

const EMPTY_FORM = { prefix: '', number: '', title: '', units: 3, grade: null, season: null, year: '' }

export default function MyCourses() {
  const { courses, addCourse, removeCourse, updateCourse, clearCourses } = useCourses()
  const gpa = useGPA()

  const [mode, setMode] = useState('upload')
  const [form, setForm] = useState(EMPTY_FORM)
  const [errors, setErrors] = useState({})
  const [clearOpen, setClearOpen] = useState(false)

  const stats = useMemo(() => {
    let units = 0
    let completed = 0
    for (const c of courses) {
      const grade = (c.grade || '').trim().toUpperCase()
      if (!NON_TRANSFERABLE.has(grade)) units += parseFloat(c.units) || 0
      if (!NOT_COMPLETED.has(grade)) completed++
    }
    return { units, completed }
  }, [courses])

  const trend = useMemo(() => termTrend(courses).filter((t) => t.cumulativeGPA != null), [courses])

  const reducedMotion = useReducedMotion(undefined, { getInitialValueInEffect: false })

  const scrollToStats = () => {
    window.scrollTo({ top: 0, behavior: reducedMotion ? 'auto' : 'smooth' })
  }

  const setField = (field) => (value) => {
    setForm((f) => ({ ...f, [field]: value }))
    if (errors[field]) setErrors((e) => ({ ...e, [field]: undefined }))
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    const next = {}
    if (!form.prefix.trim()) next.prefix = 'Enter a prefix'
    if (!form.number.trim()) next.number = 'Enter a number'
    if (!form.grade) next.grade = 'Pick a grade'
    if (!form.season) next.season = 'Pick a season'
    if (!form.year) next.year = 'Enter a year'
    if (Object.keys(next).length > 0) { setErrors(next); return }

    addCourse({
      prefix: form.prefix.trim().toUpperCase(),
      number: form.number.trim(),
      title: form.title.trim(),
      units: form.units || 0,
      grade: form.grade,
      term: formatTerm(form.season, form.year),
      source: 'manual',
    })
    setForm(EMPTY_FORM)
    setErrors({})
  }

  return (
    <>
      <Group justify="space-between" align="flex-end" mb="md" gap="md">
        <Box>
          <Title order={2}>My Courses</Title>
          <Text c="dimmed" size="sm" mt={4}>
            Track your completed courses for transfer planning.
          </Text>
        </Box>
        <Group gap="sm" align="flex-end">
          <CollegeSelect size="sm" w={260} />
          <MajorSelect size="sm" w={260} />
        </Group>
      </Group>

      <SimpleGrid cols={{ base: 1, sm: 3 }} mb="lg">
        <StatsCard
          title="Overall GPA"
          value={gpa != null ? <CountUp value={gpa} decimals={2} /> : '—'}
          subtitle={gpa == null ? 'Calculated once you add graded courses' : undefined}
        />
        <TransferUnitsCard units={stats.units} target={TRANSFER_UNIT_TARGET} />
        <StatsCard title="Courses completed" value={<CountUp value={stats.completed} />} />
      </SimpleGrid>

      {trend.length >= 2 && (
        <Paper withBorder p="md" radius="md" mb="lg">
          <Text fw={600} mb="sm">GPA trend</Text>
          <GpaTrendChart data={trend} />
        </Paper>
      )}

      <Paper withBorder p="md" radius="md" mb="lg">
        <Group justify="space-between" mb="md">
          <Text fw={600}>Add courses</Text>
          <SegmentedControl
            size="xs"
            value={mode}
            onChange={setMode}
            data={[
              { value: 'upload', label: 'Upload transcript' },
              { value: 'manual', label: 'Enter manually' },
            ]}
          />
        </Group>

        {mode === 'upload' ? (
          <TranscriptUpload onAdded={scrollToStats} />
        ) : (
          <form onSubmit={handleSubmit} noValidate>
            <SimpleGrid cols={{ base: 1, sm: 2, md: 4 }} spacing="sm">
              <TextInput
                label="Prefix"
                placeholder="e.g. MATH"
                value={form.prefix}
                onChange={(e) => setField('prefix')(e.currentTarget.value)}
                error={errors.prefix}
                required
              />
              <TextInput
                label="Number"
                placeholder="e.g. 101"
                value={form.number}
                onChange={(e) => setField('number')(e.currentTarget.value)}
                error={errors.number}
                required
              />
              <TextInput
                label="Title"
                placeholder="Optional"
                value={form.title}
                onChange={(e) => setField('title')(e.currentTarget.value)}
              />
              <NumberInput
                label="Units"
                value={form.units}
                onChange={setField('units')}
                min={0}
                max={10}
                step={0.5}
                required
              />
              <Select
                label="Grade"
                placeholder="Select"
                data={GRADE_OPTIONS}
                value={form.grade}
                onChange={setField('grade')}
                error={errors.grade}
                required
              />
              <Select
                label="Season"
                placeholder="Select"
                data={SEASONS}
                value={form.season}
                onChange={setField('season')}
                error={errors.season}
                required
              />
              <NumberInput
                label="Year"
                placeholder="e.g. 2024"
                value={form.year}
                onChange={setField('year')}
                error={errors.year}
                min={1990}
                max={2100}
                allowDecimal={false}
                hideControls
                required
              />
            </SimpleGrid>
            <Group justify="flex-end" mt="md">
              <Button type="submit">Add course</Button>
            </Group>
          </form>
        )}
      </Paper>

      <Paper withBorder p="md" radius="md">
        <Group justify="space-between" mb="sm">
          <Text fw={600}>Course history</Text>
          {courses.length > 0 && (
            <Button variant="subtle" color="red" size="xs" onClick={() => setClearOpen(true)}>
              Clear all
            </Button>
          )}
        </Group>

        {courses.length > 0 ? (
          <CourseHistoryTable
            courses={courses}
            onUpdate={updateCourse}
            onRemove={removeCourse}
          />
        ) : (
          <Stack align="center" gap="xs" py="xl">
            <Text fw={600}>No courses yet</Text>
            <Text size="sm" c="dimmed" ta="center">
              Courses you add will show up here.
            </Text>
          </Stack>
        )}
      </Paper>

      <Modal opened={clearOpen} onClose={() => setClearOpen(false)} title="Clear all courses?" centered>
        <Stack>
          <Text size="sm">This will remove all {courses.length} courses. This cannot be undone.</Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setClearOpen(false)}>Cancel</Button>
            <Button color="red" onClick={() => { clearCourses(); setClearOpen(false) }}>Clear all</Button>
          </Group>
        </Stack>
      </Modal>
    </>
  )
}
