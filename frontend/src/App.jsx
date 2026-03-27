import { Routes, Route, NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  AppShell, NavLink as MantineNavLink, Title, Group, Text, Divider, ScrollArea,
} from '@mantine/core'
import {
  IconChartBar, IconSchool, IconBook, IconBuildingCommunity,
  IconFileText, IconUser, IconBookmark,
} from '@tabler/icons-react'
import GeneralStats from './pages/GeneralStats.jsx'
import SchoolStats from './pages/SchoolStats.jsx'
import MajorStats from './pages/MajorStats.jsx'
import CampusMajors from './pages/CampusMajors.jsx'
import TransferRequirements from './pages/TransferRequirements.jsx'
import MyCourses from './pages/MyCourses.jsx'
import SavedItems from './pages/SavedItems.jsx'

const NAV_SECTIONS = [
  {
    label: 'Stats Dashboard',
    items: [
      { label: 'General Stats', path: '/', icon: IconChartBar },
      { label: 'By School', path: '/school', icon: IconSchool },
      { label: 'By Major', path: '/major', icon: IconBook },
      { label: 'By Campus', path: '/campus', icon: IconBuildingCommunity },
    ],
  },
  {
    label: 'Transfer Requirements',
    items: [
      { label: 'Transfer Requirements', path: '/requirements', icon: IconFileText },
    ],
  },
  {
    label: 'User Profile',
    items: [
      { label: 'My Courses', path: '/profile/courses', icon: IconUser },
      { label: 'Saved Schools', path: '/profile/saved', icon: IconBookmark },
    ],
  },
]

export default function App() {
  const location = useLocation()

  return (
    <AppShell
      navbar={{ width: 240, breakpoint: 0 }}
      footer={{ height: 50 }}
      padding="md"
    >
      <AppShell.Navbar p="xs" style={{ backgroundColor: '#003262' }}>
        <Title
          order={4} c="white" mb="md" px={4}
          style={{ cursor: 'pointer' }}
          component={NavLink}
          to="/"
        >
          UC Transfer Trends
        </Title>

        <ScrollArea style={{ flex: 1 }} scrollbarSize={4}>
          {NAV_SECTIONS.map((section, si) => (
            <div key={section.label}>
              {si > 0 && <Divider my="xs" color="rgba(255,255,255,0.15)" />}
              <Text size="xs" fw={700} tt="uppercase" c="rgba(255,255,255,0.5)" mb={4} px={4}>
                {section.label}
              </Text>
              {section.items.map((item) => {
                const isActive = item.path === '/'
                  ? location.pathname === '/'
                  : location.pathname.startsWith(item.path)
                return (
                  <MantineNavLink
                    key={item.path}
                    label={item.label}
                    leftSection={<item.icon size={18} color="white" />}
                    active={isActive}
                    component={NavLink}
                    to={item.path}
                    styles={{
                      root: { borderRadius: 6 },
                      label: { color: 'white' },
                    }}
                    variant="filled"
                  />
                )
              })}
            </div>
          ))}
        </ScrollArea>
      </AppShell.Navbar>

      <AppShell.Main>
        <Routes>
          <Route path="/" element={<GeneralStats />} />
          <Route path="/school" element={<SchoolStats />} />
          <Route path="/school/:school" element={<SchoolStats />} />
          <Route path="/major" element={<MajorStats />} />
          <Route path="/major/*" element={<MajorStats />} />
          <Route path="/campus" element={<CampusMajors />} />
          <Route path="/campus/:campus" element={<CampusMajors />} />
          <Route path="/requirements" element={<TransferRequirements />} />
          <Route path="/requirements/:cc" element={<TransferRequirements />} />
          <Route path="/requirements/:cc/:uc" element={<TransferRequirements />} />
          <Route path="/requirements/:cc/:uc/:major" element={<TransferRequirements />} />
          <Route path="/profile/courses" element={<MyCourses />} />
          <Route path="/profile/saved" element={<SavedItems />} />
        </Routes>
      </AppShell.Main>

      <AppShell.Footer p="sm" style={{ backgroundColor: '#003262' }}>
        <Text ta="center" c="white" size="sm">
          Data sourced from the University of California
        </Text>
      </AppShell.Footer>
    </AppShell>
  )
}
