import { useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Title, SimpleGrid, Loader, Alert, Text, Paper, UnstyledButton,
  Group, Badge, Select, Stack, Table, Divider, ThemeIcon, TextInput,
} from '@mantine/core'
import { IconCheck, IconMinus } from '@tabler/icons-react'
import {
  useArticulationColleges,
  useArticulationCampuses,
  useArticulationMajors,
  useArticulationDetail,
  useMajorStats,
} from '../hooks/useApi'
import { useCourses, useGPA } from '../hooks/useUserData'
import { buildUserCourseMap, checkRequirementSatisfied, getMatchedCourseKeys, computeRequirementStats, parsePathwayGroups, normalizeCourseKey } from '../utils/courseMatch'
import { UC_COLORS } from '../utils/ucColors'

const UC_LABELS = {
  ucb: 'UC Berkeley', ucd: 'UC Davis', uci: 'UC Irvine',
  ucla: 'UCLA', ucm: 'UC Merced', ucr: 'UC Riverside',
  ucsb: 'UC Santa Barbara', ucsc: 'UC Santa Cruz', ucsd: 'UC San Diego',
}

function ucColor(code) {
  return UC_COLORS[code.toUpperCase()] || '#666'
}

// Strip degree suffix from articulation major names
// e.g. "Computer Science, B.A." → "Computer Science"
function stripDegree(majorName) {
  return majorName
    .replace(/,?\s*(B\.?[AS]\.?|M\.?[AS]\.?|Minor)\.?\s*$/i, '')
    .trim()
}

function gpaStatus(gpa, min, max) {
  if (gpa == null || min == null) return null
  if (gpa < min) return 'below'
  if (max != null && gpa > max) return 'above'
  return 'within'
}

const GPA_STATUS_STYLES = {
  below: { color: '#e03131', label: 'Below Range' },
  within: { color: '#2f9e44', label: 'Within Range' },
  above: { color: '#1971c2', label: 'Above Range' },
}

export default function TransferRequirements() {
  const { cc, uc, major: majorSlug } = useParams()
  const navigate = useNavigate()

  if (cc && uc && majorSlug) {
    return <AgreementDetail cc={cc} uc={uc} majorSlug={majorSlug} navigate={navigate} />
  }

  if (cc && uc) {
    return <MajorList cc={cc} uc={uc} navigate={navigate} />
  }

  return <SelectorView cc={cc} navigate={navigate} />
}


function SelectorView({ cc: urlCC, navigate }) {
  const { data: colleges, loading: colLoading } = useArticulationColleges()
  const [selectedCC, setSelectedCC] = useState(urlCC || null)
  const { data: campuses, loading: ucLoading } = useArticulationCampuses(selectedCC)

  const ccOptions = useMemo(() =>
    (colleges || []).map((c) => ({ value: c.code, label: c.name })),
    [colleges]
  )

  return (
    <>
      <Title order={2} mb="md">Transfer Requirements</Title>
      <Text c="dimmed" size="sm" mb="lg">
        View course articulation agreements from assist.org. Select your community college
        and the UC campus you want to transfer to.
      </Text>

      {colLoading && <Loader m="xl" />}

      {!colLoading && ccOptions.length > 0 && (
        <Select
          label="Community College"
          placeholder="Select your community college"
          data={ccOptions}
          value={selectedCC}
          onChange={(val) => {
            setSelectedCC(val)
            if (urlCC) navigate('/requirements')
          }}
          searchable
          clearable
          allowDeselect={false}
          mb="lg"
          maw={400}
        />
      )}

      {ucLoading && <Loader size="sm" mt="md" />}

      {selectedCC && campuses && campuses.length > 0 && (
        <>
          <Title order={4} mb="sm">Select a UC Campus</Title>
          <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }}>
            {campuses.map((campus) => {
              const color = ucColor(campus.code)
              return (
                <UnstyledButton
                  key={campus.code}
                  onClick={() => navigate(`/requirements/${selectedCC}/${campus.code}`)}
                >
                  <Paper
                    withBorder
                    p="md"
                    radius="md"
                    style={{
                      cursor: 'pointer',
                      transition: 'box-shadow 150ms, border-color 150ms',
                      borderLeft: `4px solid ${color}`,
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)' }}
                    onMouseLeave={(e) => { e.currentTarget.style.boxShadow = '' }}
                  >
                    <Text fw={600}>{UC_LABELS[campus.code] || campus.name}</Text>
                    <Text size="xs" c="dimmed">{campus.name}</Text>
                  </Paper>
                </UnstyledButton>
              )
            })}
          </SimpleGrid>
        </>
      )}

      {selectedCC && campuses && campuses.length === 0 && (
        <Alert color="yellow" mt="md">No articulation data found for this college.</Alert>
      )}
    </>
  )
}


function MajorList({ cc, uc, navigate }) {
  const { data: majors, loading, error } = useArticulationMajors(cc, uc)
  const [search, setSearch] = useState('')

  const filtered = useMemo(() => {
    if (!majors) return []
    if (!search) return majors
    const q = search.toLowerCase()
    return majors.filter((m) => m.name.toLowerCase().includes(q))
  }, [majors, search])

  const color = ucColor(uc)

  return (
    <>
      <Text
        c="dimmed" size="sm" mb="md"
        style={{ cursor: 'pointer' }}
        onClick={() => navigate('/requirements')}
      >
        &larr; Back to campus selection
      </Text>

      <Group mb="md" align="flex-end">
        <div>
          <Title order={2}>
            {UC_LABELS[uc] || uc.toUpperCase()}
          </Title>
          <Text size="sm" c="dimmed">
            Articulation agreements from {cc.toUpperCase()}
          </Text>
        </div>
        <Badge
          size="lg" variant="light"
          style={{ color, borderColor: color, backgroundColor: `${color}15` }}
        >
          {filtered.length} majors
        </Badge>
      </Group>

      <TextInput
        placeholder="Search majors..."
        value={search}
        onChange={(e) => setSearch(e.currentTarget.value)}
        mb="lg"
        maw={400}
      />

      {loading && <Loader m="xl" />}
      {error && <Alert color="red" title="Error">{error}</Alert>}

      <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }}>
        {filtered.map((m) => (
          <UnstyledButton
            key={m.slug}
            onClick={() => navigate(`/requirements/${cc}/${uc}/${m.slug}`)}
          >
            <Paper
              withBorder
              p="sm"
              radius="md"
              style={{
                cursor: 'pointer',
                transition: 'box-shadow 150ms',
                borderLeft: `3px solid ${color}`,
              }}
              onMouseEnter={(e) => { e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)' }}
              onMouseLeave={(e) => { e.currentTarget.style.boxShadow = '' }}
            >
              <Text size="sm" fw={500}>{m.name}</Text>
              <Group gap={8} mt={4}>
                <Text size="xs" c="dimmed">{m.academic_year}</Text>
                <Badge size="xs" variant="light" color="blue">
                  {m.row_count} course{m.row_count !== 1 ? 's' : ''}
                </Badge>
              </Group>
            </Paper>
          </UnstyledButton>
        ))}
      </SimpleGrid>

      {!loading && filtered.length === 0 && (
        <Text c="dimmed" ta="center" mt="xl">No majors found.</Text>
      )}
    </>
  )
}


function AgreementDetail({ cc, uc, majorSlug, navigate }) {
  const { data: agreement, loading, error } = useArticulationDetail(cc, uc, majorSlug)
  const { courses } = useCourses()
  const overallGPA = useGPA()
  const color = ucColor(uc)

  // Fetch admit GPA range for this major from transfer stats
  const baseMajor = agreement ? stripDegree(agreement.major) : null
  const { data: majorStatsData } = useMajorStats(baseMajor)

  // Find the latest year's GPA range for this UC campus
  const admitGpaInfo = useMemo(() => {
    if (!majorStatsData) return null
    const ucCode = uc.toUpperCase()
    const rows = majorStatsData
      .filter((r) => r.university === ucCode && r.avg_admit_gpa_min != null)
      .sort((a, b) => b.year - a.year)
    if (rows.length === 0) return null
    const latest = rows[0]
    return {
      min: parseFloat(latest.avg_admit_gpa_min),
      max: latest.avg_admit_gpa_max != null ? parseFloat(latest.avg_admit_gpa_max) : null,
      year: latest.year,
    }
  }, [majorStatsData, uc])

  const userCourseMap = useMemo(() => buildUserCourseMap(courses), [courses])

  const matchedKeys = useMemo(() => {
    if (!agreement) return new Set()
    return getMatchedCourseKeys(agreement, userCourseMap)
  }, [agreement, userCourseMap])

  const majorGPA = useGPA(matchedKeys.size > 0 ? matchedKeys : undefined)

  const reqStats = useMemo(() => {
    return computeRequirementStats(agreement, userCourseMap)
  }, [agreement, userCourseMap])

  // Build a set of receiving course keys that are in pathway groups,
  // and a map of which rows should show an "OR" separator before them.
  const pathwayInfo = useMemo(() => {
    if (!agreement) return { groupedKeys: new Set(), orBeforeKeys: new Set() }
    const groups = parsePathwayGroups(agreement.notes)
    const groupedKeys = new Set()
    const orBeforeKeys = new Set()

    for (const group of groups) {
      for (const key of group.receivingKeys) groupedKeys.add(key)

      // Find which rows start a new pathway option within the group.
      // Walk through all rows in order; when a row's receiving key belongs to
      // a DIFFERENT pathway than the previous grouped row, mark it with OR.
      const allRows = (agreement.sections || []).flatMap((s) => s.rows || [])
      let prevPathwayIdx = -1
      for (const row of allRows) {
        const rk = row.receiving_courses?.courses?.[0]
          ? normalizeCourseKey(row.receiving_courses.courses[0].prefix, row.receiving_courses.courses[0].number)
          : null
        if (!rk || !group.receivingKeys.has(rk)) continue

        const pathwayIdx = group.pathways.findIndex((p) => p.includes(rk))
        if (prevPathwayIdx !== -1 && pathwayIdx !== prevPathwayIdx) {
          orBeforeKeys.add(rk)
        }
        prevPathwayIdx = pathwayIdx
      }
    }

    return { groupedKeys, orBeforeKeys }
  }, [agreement])

  const hasCourses = courses.length > 0
  const overallStatus = admitGpaInfo ? gpaStatus(overallGPA, admitGpaInfo.min, admitGpaInfo.max) : null
  const majorStatus = admitGpaInfo ? gpaStatus(majorGPA, admitGpaInfo.min, admitGpaInfo.max) : null

  if (loading) return <Loader m="xl" />
  if (error) return <Alert color="red" title="Error">{error}</Alert>
  if (!agreement) return null

  return (
    <>
      <Text
        c="dimmed" size="sm" mb="md"
        style={{ cursor: 'pointer' }}
        onClick={() => navigate(`/requirements/${cc}/${uc}`)}
      >
        &larr; Back to majors
      </Text>

      <Paper withBorder p="lg" radius="md" mb="lg" style={{ borderLeft: `4px solid ${color}` }}>
        <Title order={2} mb={4}>{agreement.major}</Title>
        <Group gap="xs">
          <Badge size="md" variant="light"
            style={{ color, borderColor: color, backgroundColor: `${color}15` }}
          >
            {UC_LABELS[uc] || uc.toUpperCase()}
          </Badge>
          <Text size="sm" c="dimmed">
            {agreement.academic_year}
          </Text>
        </Group>
        <Text size="sm" mt="xs" c="dimmed">
          From: {agreement.sending_institution} &rarr; {agreement.receiving_institution}
        </Text>
      </Paper>

      {admitGpaInfo && (
        <Paper withBorder p="md" radius="md" mb="lg" bg="gray.0">
          <Text size="xs" c="dimmed" tt="uppercase" fw={700} mb="xs">
            Admit GPA Range - 25th to 75th Percentile ({admitGpaInfo.year})
          </Text>
          <Text size="lg" fw={700}>
            {admitGpaInfo.min.toFixed(2)} - {admitGpaInfo.max != null ? admitGpaInfo.max.toFixed(2) : '?'}
          </Text>

          {hasCourses && (
            <Group gap="lg" mt="sm">
              {overallGPA != null && overallStatus && (
                <div>
                  <Text size="xs" c="dimmed">Overall GPA: {overallGPA.toFixed(2)}</Text>
                  <Badge
                    size="sm"
                    variant="light"
                    color={GPA_STATUS_STYLES[overallStatus].color}
                    style={{ color: GPA_STATUS_STYLES[overallStatus].color }}
                  >
                    {GPA_STATUS_STYLES[overallStatus].label}
                  </Badge>
                </div>
              )}
              {matchedKeys.size > 0 && majorGPA != null && majorStatus && (
                <div>
                  <Text size="xs" c="dimmed">Major GPA: {majorGPA.toFixed(2)}</Text>
                  <Badge
                    size="sm"
                    variant="light"
                    color={GPA_STATUS_STYLES[majorStatus].color}
                    style={{ color: GPA_STATUS_STYLES[majorStatus].color }}
                  >
                    {GPA_STATUS_STYLES[majorStatus].label}
                  </Badge>
                </div>
              )}
            </Group>
          )}
        </Paper>
      )}

      {hasCourses && (
        <Paper withBorder p="md" radius="md" mb="lg" bg="blue.0">
          <Group gap="lg">
            <div>
              <Text size="xs" c="dimmed" tt="uppercase" fw={700}>Requirements Met</Text>
              <Text size="lg" fw={700}>
                {reqStats.satisfied} of {reqStats.total}
              </Text>
            </div>
            <Divider orientation="vertical" />
            <div>
              <Text size="xs" c="dimmed" tt="uppercase" fw={700}>Overall GPA</Text>
              <Text size="lg" fw={700}>{overallGPA != null ? overallGPA.toFixed(2) : '-'}</Text>
            </div>
            {matchedKeys.size > 0 && (
              <>
                <Divider orientation="vertical" />
                <div>
                  <Text size="xs" c="dimmed" tt="uppercase" fw={700}>Major GPA</Text>
                  <Text size="lg" fw={700}>{majorGPA != null ? majorGPA.toFixed(2) : '-'}</Text>
                </div>
              </>
            )}
          </Group>
        </Paper>
      )}

      {agreement.notes && agreement.notes.length > 0 && (
        <Paper withBorder p="md" radius="md" mb="lg" bg="gray.0">
          <Title order={5} mb="xs">Important Information</Title>
          {agreement.notes.map((note, i) => (
            <Text key={i} size="sm" mb="xs" style={{ lineHeight: 1.6 }}>
              {note}
            </Text>
          ))}
        </Paper>
      )}

      {agreement.sections && agreement.sections.map((section, si) => (
        <div key={si}>
          {section.section_title && (
            <Title order={4} mt="lg" mb="sm">{section.section_title}</Title>
          )}

          <Paper withBorder radius="md" style={{ overflow: 'hidden' }}>
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th style={{ width: '45%', backgroundColor: `${color}10` }}>
                    <Text size="xs" fw={700} tt="uppercase">
                      {UC_LABELS[uc] || uc.toUpperCase()} Course
                    </Text>
                  </Table.Th>
                  <Table.Th style={{ width: '10%' }}></Table.Th>
                  <Table.Th style={{ width: '45%' }}>
                    <Text size="xs" fw={700} tt="uppercase">
                      {cc.toUpperCase()} Course
                    </Text>
                  </Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {section.rows.map((row, ri) => (
                  <CourseRow key={ri} row={row} color={color} userCourseMap={userCourseMap} hasCourses={hasCourses} pathwayInfo={pathwayInfo} />
                ))}
              </Table.Tbody>
            </Table>
          </Paper>
        </div>
      ))}
    </>
  )
}


function CourseRow({ row, color, userCourseMap, hasCourses, pathwayInfo }) {
  const receiving = row.receiving_courses
  const sending = row.sending_courses
  const noArticulation = sending.logic === 'NO_ARTICULATION'

  const receivingKey = receiving?.courses?.[0]
    ? normalizeCourseKey(receiving.courses[0].prefix, receiving.courses[0].number)
    : null
  const showOrSeparator = receivingKey && pathwayInfo?.orBeforeKeys?.has(receivingKey)

  const status = hasCourses ? checkRequirementSatisfied(sending, userCourseMap) : 'none'

  const rowStyle = {}
  if (hasCourses && status === 'satisfied') {
    rowStyle.backgroundColor = 'rgba(64, 192, 87, 0.12)'
  } else if (hasCourses && status === 'partial') {
    rowStyle.backgroundColor = 'rgba(255, 212, 59, 0.15)'
  }

  return (
    <>
      {showOrSeparator && (
        <Table.Tr>
          <Table.Td colSpan={3} style={{ textAlign: 'center', padding: '6px 0' }}>
            <Badge size="sm" variant="light" color="orange" radius="sm">OR</Badge>
          </Table.Td>
        </Table.Tr>
      )}
      <Table.Tr style={rowStyle}>
      <Table.Td style={{ verticalAlign: 'top' }}>
        <Group gap={6} wrap="nowrap">
          {hasCourses && status === 'satisfied' && (
            <ThemeIcon size="xs" color="green" variant="light" radius="xl">
              <IconCheck size={10} />
            </ThemeIcon>
          )}
          {hasCourses && status === 'partial' && (
            <ThemeIcon size="xs" color="yellow" variant="light" radius="xl">
              <IconMinus size={10} />
            </ThemeIcon>
          )}
          <CourseGroupDisplay group={receiving} accentColor={color} />
        </Group>
      </Table.Td>

      <Table.Td style={{ textAlign: 'center', verticalAlign: 'middle' }}>
        <Text size="lg" c="dimmed">&rarr;</Text>
      </Table.Td>

      <Table.Td style={{ verticalAlign: 'top' }}>
        {noArticulation ? (
          <Text size="sm" c="red" fs="italic">No Course Articulated</Text>
        ) : (
          <CourseGroupDisplay group={sending} />
        )}
      </Table.Td>
    </Table.Tr>
    </>
  )
}


function CourseGroupDisplay({ group, accentColor }) {
  if (!group.courses || group.courses.length === 0) return null

  return (
    <Stack gap={2}>
      {group.courses.map((course, i) => (
        <div key={i}>
          {i > 0 && group.logic !== 'SINGLE' && (
            <Badge
              size="xs"
              variant="light"
              color={group.logic === 'OR' ? 'green' : 'blue'}
              my={2}
            >
              {group.logic}
            </Badge>
          )}
          <Group gap={6} wrap="nowrap">
            <Text size="sm" fw={600} style={accentColor ? { color: accentColor } : {}}>
              {course.prefix} {course.number}
            </Text>
            {course.units && (
              <Text size="xs" c="dimmed">({course.units})</Text>
            )}
          </Group>
          {course.title && (
            <Text size="xs" c="dimmed" ml={2}>{course.title}</Text>
          )}
        </div>
      ))}
    </Stack>
  )
}
