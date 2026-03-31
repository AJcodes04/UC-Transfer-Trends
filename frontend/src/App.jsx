import { Routes, Route, NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  AppShell, NavLink as MantineNavLink, Title, Group, Text, Divider, ScrollArea, Burger,
} from '@mantine/core'
import { useDisclosure, useMediaQuery } from '@mantine/hooks'
import {
  IconChartBar, IconSchool, IconBook, IconBuildingCommunity,
  IconFileText, IconUser, IconBookmark,
} from '@tabler/icons-react'
import './nav.css'
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
      { label: 'By College/School', path: '/school', icon: IconSchool },
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
      { label: 'Watchlist', path: '/profile/saved', icon: IconBookmark },
    ],
  },
]

export default function App() {
  const location = useLocation()
  const [opened, { toggle, close }] = useDisclosure()
  const isMobile = useMediaQuery('(max-width: 48em)')

  return (
    <AppShell
      header={isMobile ? { height: 60 } : undefined}
      navbar={{ width: 240, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      footer={{ height: 70 }}
      padding="md"
    >
      <AppShell.Header hiddenFrom="sm" style={{ backgroundColor: '#0E4D84' }}>
        <Group h="100%" px="md">
          <Burger opened={opened} onClick={toggle} color="white" size="sm" />
          <Title
            order={4} c="white"
            style={{ cursor: 'pointer', textDecoration: 'none' }}
            component={NavLink}
            to="/"
            onClick={close}
          >
            UC Transfer Trends
          </Title>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="xs" style={{ backgroundColor: '#0E4D84' }}>
        <Title
          order={4} c="white" mb="md" px={4}
          style={{ cursor: 'pointer', textDecoration: 'none' }}
          component={NavLink}
          to="/"
          onClick={close}
          visibleFrom="sm"
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
                    onClick={close}
                    className="navLink"
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

      <AppShell.Footer pt="sm" pb="md" px="sm" style={{ backgroundColor: '#0E4D84' }}>
        <Text ta="center" c="white" size="sm">
          Data sourced from the University of California
        </Text>
        <Text ta="center" c="rgba(255,255,255,0.6)" size="xs">
          The UC system may not publish all transfer data. Some majors or years may be incomplete or missing.
        </Text>
      </AppShell.Footer>
    </AppShell>
  )
}
