import { useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Title, SimpleGrid, Loader, Alert, Text, Paper, UnstyledButton,
  Group, Badge, Select, Stack, Table, Divider, ThemeIcon, TextInput, Box,
  Anchor,
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
import {
  buildUserCourseMap,
  checkRequirementSatisfied,
  checkGroupSatisfied,
  getMatchedCourseKeys,
  computeRequirementStats,
  normalizeCourseKey,
} from '../utils/courseMatch'
import { UC_COLORS } from '../utils/ucColors'

const UC_LABELS = {
  ucb: 'UC Berkeley', ucd: 'UC Davis', uci: 'UC Irvine',
  ucla: 'UCLA', ucm: 'UC Merced', ucr: 'UC Riverside',
  ucsb: 'UC Santa Barbara', ucsc: 'UC Santa Cruz', ucsd: 'UC San Diego',
}

function Linkify({ children }) {
  if (typeof children !== 'string') return children
  const parts = children.split(/(https?:\/\/[^\s),]+)/g)
  if (parts.length === 1) return children
  return parts.map((part, i) =>
    /^https?:\/\//.test(part) ? (
      <Anchor key={i} href={part} target="_blank" rel="noopener noreferrer" size="sm">
        {part}
      </Anchor>
    ) : (
      part
    )
  )
}

// Common filler words to ignore when matching recommended descriptions to course titles
const STOP_WORDS = new Set([
  'a', 'an', 'the', 'of', 'and', 'or', 'with', 'for', 'in', 'to', 'from',
  'two', 'three', 'one', 'four', 'lab', 'laboratory', 'based', 'semesters',
  'quarters', 'semester', 'quarter', 'year', 'completion',
])

// Map full department names (from notes) to abbreviated prefixes (in course data)
const DEPT_NAME_TO_PREFIX = {
  'computer science': 'CMPSC',
  'math': 'MATH',
  'mathematics': 'MATH',
  'chemistry': 'CHEM',
  'physics': 'PHYS',
  'electrical and computer engineering': 'ECE',
  'mechanical engineering': 'ME',
  'chemical engineering': 'CH E',
}

/**
 * Parse notes for "STRONGLY RECOMMENDED" courses.
 * Returns { keywords: string[][], courseCodes: Set<string> }
 *   - keywords: fuzzy description words (UCLA-style: "Completion of X are STRONGLY RECOMMENDED")
 *   - courseCodes: exact "PREFIX NUMBER" strings (UCSB-style: note starts with "STRONGLY RECOMMENDED")
 */
function parseRecommendedInfo(notes) {
  const keywords = []
  const courseCodes = new Set()
  if (!notes || !notes.length) return { keywords, courseCodes }

  for (const note of notes) {
    // Pattern 1 (UCLA-style): "Completion of X are/is STRONGLY RECOMMENDED"
    const beforeMatch = note.match(/(?:completion of|complete)\s+(.+?)\s+(?:are|is)\s+STRONGLY\s+RECOMMENDED/i)
    if (beforeMatch) {
      const cleaned = beforeMatch[1].replace(/[\w/]+\s+(?:semesters?|quarters?)\s+(?:of\s+)?/gi, '')
      const parts = cleaned.split(/,\s*(?:and\s+)?|\s+and\s+/).map((s) => s.trim()).filter(Boolean)
      for (const part of parts) {
        const words = part.toLowerCase().split(/\s+/).filter((w) => w.length > 2 && !STOP_WORDS.has(w))
        if (words.length) keywords.push(words)
      }
    }

    // Pattern 2 (UCSB-style): Note starts with "STRONGLY RECOMMENDED"
    const stripped = note.trim()
    if (/^STRONGLY\s+RECOMMENDED/i.test(stripped)) {
      // Extract text after parenthetical disclaimer, up to "Note :" or "Additional"
      let courseText = stripped
        .replace(/^STRONGLY\s+RECOMMENDED[^)]*\)\s*/i, '')
        .replace(/\s*(?:Note\s*:|Additional\s).*/i, '')
        .trim()

      // Extract abbreviated codes: "PHYS 1, 2, 3, 3L" → PHYS 1, PHYS 2, etc.
      const abbrRegex = /\b([A-Z]{2,}(?:\s[A-Z]{2,})?)\s+([\dA-Za-z]+(?:(?:,\s*|\s*;\s*)[\dA-Za-z]+)*)/g
      let m
      while ((m = abbrRegex.exec(courseText)) !== null) {
        const prefix = m[1]
        const nums = m[2].split(/[,;]\s*/).map((n) => n.trim()).filter(Boolean)
        for (const num of nums) {
          if (/\d/.test(num)) {
            courseCodes.add(`${prefix} ${num}`.toUpperCase())
          }
        }
      }

      // Extract full department name codes: "Computer Science 32, 64" → CMPSC 32, CMPSC 64
      const deptRegex = /([A-Z][a-z]+(?:\s+(?:and\s+)?[A-Z][a-z]+)*)\s+([\dA-Za-z]+(?:(?:,\s*)[\dA-Za-z]+)*)/g
      while ((m = deptRegex.exec(courseText)) !== null) {
        const deptName = m[1].toLowerCase()
        const prefix = DEPT_NAME_TO_PREFIX[deptName]
        if (!prefix) continue
        const nums = m[2].split(/,\s*/).map((n) => n.trim()).filter(Boolean)
        for (const num of nums) {
          if (/\d/.test(num)) {
            courseCodes.add(`${prefix} ${num}`.toUpperCase())
          }
        }
      }
    }
  }

  return { keywords, courseCodes }
}

/**
 * Check if a course row matches any recommended description or course code.
 */
function isRowRecommended(row, recommendedInfo) {
  if (!recommendedInfo) return false
  const { keywords, courseCodes } = recommendedInfo
  if (!keywords.length && !courseCodes.size) return false

  const receivingCourses = row.receiving_courses?.courses || []

  // Check exact course code matches against receiving courses
  if (courseCodes.size > 0) {
    for (const c of receivingCourses) {
      const code = `${c.prefix} ${c.number}`.toUpperCase()
      if (courseCodes.has(code)) return true
    }
  }

  // Check fuzzy keyword matches against course titles
  if (keywords.length > 0) {
    const titles = [
      ...receivingCourses.map((c) => (c.title || '').toLowerCase()),
      ...(row.sending_courses?.courses || []).map((c) => (c.title || '').toLowerCase()),
      ...receivingCourses.map((c) => `${c.prefix} ${c.number}`.toLowerCase()),
    ]
    for (const kws of keywords) {
      for (const title of titles) {
        const matched = kws.filter((kw) => title.includes(kw))
        if (matched.length >= Math.max(1, Math.ceil(kws.length * 0.5))) {
          return true
        }
      }
    }
  }

  return false
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

  const baseMajor = agreement ? stripDegree(agreement.major) : null
  const { data: majorStatsData } = useMajorStats(baseMajor)

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

  const recommendedInfo = useMemo(() => {
    return parseRecommendedInfo(agreement?.notes)
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
              <Linkify>{note}</Linkify>
            </Text>
          ))}
        </Paper>
      )}

      {agreement.sections && agreement.sections.map((section, si) => (
        <SectionDisplay
          key={si}
          section={section}
          uc={uc}
          cc={cc}
          color={color}
          userCourseMap={userCourseMap}
          hasCourses={hasCourses}
          recommendedInfo={recommendedInfo}
        />
      ))}
    </>
  )
}


/**
 * SectionDisplay — renders one AgreementSection.
 *
 * Handles BOTH the new format (section.groups) and old format (section.rows).
 * New format: groups with optional labels and multi-option SELECT_ONE groups.
 * Old format: flat rows rendered the same as COMPLETE_ALL single-option groups.
 */
function SectionDisplay({ section, uc, cc, color, userCourseMap, hasCourses, recommendedInfo }) {
  const groups = section.groups || []
  const oldRows = section.rows || []

  return (
    <div>
      {section.section_title && (
        <Title order={4} mt="lg" mb="sm">{section.section_title}</Title>
      )}

      {groups.length > 0 ? (
        // ── New format: render each group ──────────────────────────────────
        <Stack gap="sm">
          {groups.map((group, gi) => (
            <GroupDisplay
              key={group.group_id || gi}
              group={group}
              groupIndex={gi}
              uc={uc}
              cc={cc}
              color={color}
              userCourseMap={userCourseMap}
              hasCourses={hasCourses}
              recommendedInfo={recommendedInfo}
            />
          ))}
        </Stack>
      ) : (
        // ── Old format fallback: flat rows table ───────────────────────────
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
              {oldRows.map((row, ri) => (
                <CourseRow
                  key={ri}
                  row={row}
                  color={color}
                  userCourseMap={userCourseMap}
                  hasCourses={hasCourses}
                  recommendedInfo={recommendedInfo}
                />
              ))}
            </Table.Tbody>
          </Table>
        </Paper>
      )}
    </div>
  )
}


/**
 * GroupDisplay — renders one RequirementGroup.
 *
 * For COMPLETE_ALL: a plain table of rows (same as old format).
 * For SELECT_ONE:   a bordered box with a "Select A or B" header and
 *                   each option shown as a sub-table with an OR separator.
 * For SELECT_N:     a table with a "Complete N from the following" header.
 */
function GroupDisplay({ group, groupIndex, uc, cc, color, userCourseMap, hasCourses, recommendedInfo }) {
  const logic = group.group_logic || 'COMPLETE_ALL'
  const options = group.options || []
  const label = group.group_label

  // Compute satisfaction status for the whole group (for visual highlight)
  const groupStatus = hasCourses ? checkGroupSatisfied(group, userCourseMap) : 'none'

  const groupBorderStyle = {}
  if (hasCourses && groupStatus === 'satisfied') {
    groupBorderStyle.borderLeft = '3px solid rgba(64, 192, 87, 0.7)'
  } else if (hasCourses && groupStatus === 'partial') {
    groupBorderStyle.borderLeft = '3px solid rgba(255, 212, 59, 0.7)'
  }

  if (logic === 'SELECT_ONE') {
    // ── SELECT_ONE: "Select A or B" — show each option as a separate block ──
    return (
      <Paper
        withBorder
        radius="md"
        style={{ overflow: 'hidden', ...groupBorderStyle }}
      >
        {/* Group header with label */}
        <Box
          px="md"
          py="xs"
          style={{
            backgroundColor: `${color}08`,
            borderBottom: '1px solid var(--mantine-color-gray-2)',
          }}
        >
          <Group gap="xs" align="center">
            {hasCourses && groupStatus === 'satisfied' && (
              <ThemeIcon size="xs" color="green" variant="light" radius="xl">
                <IconCheck size={10} />
              </ThemeIcon>
            )}
            {hasCourses && groupStatus === 'partial' && (
              <ThemeIcon size="xs" color="yellow" variant="light" radius="xl">
                <IconMinus size={10} />
              </ThemeIcon>
            )}
            <Text size="xs" fw={700} tt="uppercase" c="dimmed">
              {label || 'Select one option'}
            </Text>
          </Group>
        </Box>

        {/* Each option with OR separators between them */}
        {options.map((option, oi) => (
          <div key={oi}>
            {oi > 0 && (
              <Box
                py="xs"
                style={{
                  textAlign: 'center',
                  borderTop: '1px solid var(--mantine-color-gray-2)',
                  borderBottom: '1px solid var(--mantine-color-gray-2)',
                  backgroundColor: 'var(--mantine-color-gray-0)',
                }}
              >
                <Badge size="sm" variant="light" color="orange" radius="sm">OR</Badge>
              </Box>
            )}
            <OptionTable
              option={option}
              uc={uc}
              cc={cc}
              color={color}
              userCourseMap={userCourseMap}
              hasCourses={hasCourses}
              showHeader={oi === 0}
              optionLabel={option.option_label}
              recommendedInfo={recommendedInfo}
            />
          </div>
        ))}
      </Paper>
    )
  }

  if (logic === 'SELECT_N') {
    // ── SELECT_N: "Complete N from the following" — show pool with header ──
    const allRows = options.flatMap((o) => o.rows || [])
    return (
      <Paper
        withBorder
        radius="md"
        style={{ overflow: 'hidden', ...groupBorderStyle }}
      >
        {/* Group header */}
        <Box
          px="md"
          py="xs"
          style={{
            backgroundColor: `${color}08`,
            borderBottom: '1px solid var(--mantine-color-gray-2)',
          }}
        >
          <Group gap="xs" align="center">
            {hasCourses && groupStatus === 'satisfied' && (
              <ThemeIcon size="xs" color="green" variant="light" radius="xl">
                <IconCheck size={10} />
              </ThemeIcon>
            )}
            {hasCourses && groupStatus === 'partial' && (
              <ThemeIcon size="xs" color="yellow" variant="light" radius="xl">
                <IconMinus size={10} />
              </ThemeIcon>
            )}
            <Text size="xs" fw={700} tt="uppercase" c="dimmed">
              {label || `Complete ${group.select_n || 1} from the following`}
            </Text>
          </Group>
        </Box>

        {/* Rows with OR separators between them */}
        <Table>
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
            {allRows.map((row, ri) => (
              <>
                {ri > 0 && (
                  <Table.Tr key={`or-${ri}`}>
                    <Table.Td colSpan={3} style={{ textAlign: 'center', padding: '4px 0' }}>
                      <Badge size="xs" variant="light" color="orange" radius="sm">OR</Badge>
                    </Table.Td>
                  </Table.Tr>
                )}
                <CourseRow
                  key={ri}
                  row={row}
                  color={color}
                  userCourseMap={userCourseMap}
                  hasCourses={hasCourses}
                  recommendedInfo={recommendedInfo}
                />
              </>
            ))}
          </Table.Tbody>
        </Table>
      </Paper>
    )
  }

  // ── COMPLETE_ALL (default) — plain table, no special header needed ──────
  const allRows = options.flatMap((o) => o.rows || [])
  return (
    <Paper
      withBorder
      radius="md"
      style={{ overflow: 'hidden', ...groupBorderStyle }}
    >
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
          {allRows.map((row, ri) => (
            <CourseRow
              key={ri}
              row={row}
              color={color}
              userCourseMap={userCourseMap}
              hasCourses={hasCourses}
              recommendedInfo={recommendedInfo}
            />
          ))}
        </Table.Tbody>
      </Table>
    </Paper>
  )
}


/**
 * OptionTable — renders one pathway option within a SELECT_ONE group.
 *
 * Shows an optional "Option A / Option B" label above the rows.
 */
function OptionTable({ option, uc, cc, color, userCourseMap, hasCourses, showHeader, optionLabel, recommendedInfo }) {
  const rows = option.rows || []

  return (
    <div>
      {optionLabel && (
        <Box
          px="md"
          py={4}
          style={{
            backgroundColor: `${color}05`,
          }}
        >
          <Text size="xs" c="dimmed" fw={600}>Option {optionLabel}</Text>
        </Box>
      )}
      <Table>
        {showHeader && (
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
        )}
        <Table.Tbody>
          {rows.map((row, ri) => (
            <CourseRow
              key={ri}
              row={row}
              color={color}
              userCourseMap={userCourseMap}
              hasCourses={hasCourses}
              recommendedInfo={recommendedInfo}
            />
          ))}
        </Table.Tbody>
      </Table>
    </div>
  )
}


function CourseRow({ row, color, userCourseMap, hasCourses, recommendedInfo }) {
  const receiving = row.receiving_courses
  const sending = row.sending_courses
  const noArticulation = sending.logic === 'NO_ARTICULATION'
  const recommended = recommendedInfo ? isRowRecommended(row, recommendedInfo) : false

  const status = hasCourses
    ? (sending.logic === 'NO_ARTICULATION' ? 'none' : (() => {
        const matches = (sending.courses || []).filter((c) =>
          userCourseMap.has(normalizeCourseKey(c.prefix, c.number))
        )
        if (matches.length === 0) return 'none'
        if (sending.logic === 'OR' || sending.logic === 'SINGLE') return 'satisfied'
        if (matches.length === sending.courses.length) return 'satisfied'
        return 'partial'
      })())
    : 'none'

  const rowStyle = {}
  if (hasCourses && status === 'satisfied') {
    rowStyle.backgroundColor = 'rgba(64, 192, 87, 0.12)'
  } else if (hasCourses && status === 'partial') {
    rowStyle.backgroundColor = 'rgba(255, 212, 59, 0.15)'
  }

  return (
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
          <div>
            <CourseGroupDisplay group={receiving} accentColor={color} />
            {recommended && (
              <Badge size="xs" variant="light" color="grape" mt={4}>
                Strongly Recommended
              </Badge>
            )}
          </div>
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
