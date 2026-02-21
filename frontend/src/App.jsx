import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { AppShell, NavLink as MantineNavLink, Title, Group, Text } from '@mantine/core'
import GeneralStats from './pages/GeneralStats.jsx'
import SchoolStats from './pages/SchoolStats.jsx'
import MajorStats from './pages/MajorStats.jsx'

const NAV_ITEMS = [
  { label: 'General Stats', path: '/' },
  { label: 'By School', path: '/school' },
  { label: 'By Major', path: '/major' },
]

export default function App() {
  const location = useLocation()

  return (
    <AppShell
      navbar={{ width: 220, breakpoint: 'sm' }}
      footer={{ height: 50 }}
      padding="md"
    >
      <AppShell.Navbar p="md" style={{ backgroundColor: '#003262' }}>
        <Title order={4} mb="md" c="white">UC Transfer Trends</Title>
        {NAV_ITEMS.map((item) => (
          <MantineNavLink
            key={item.path}
            label={item.label}
            component={NavLink}
            to={item.path}
            active={
              item.path === '/'
                ? location.pathname === '/'
                : location.pathname.startsWith(item.path)
            }
            styles={{
              root: { borderRadius: 6 },
              label: { color: 'white' },
            }}
            variant="filled"
          />
        ))}
      </AppShell.Navbar>

      <AppShell.Main>
        <Routes>
          <Route path="/" element={<GeneralStats />} />
          <Route path="/school" element={<SchoolStats />} />
          <Route path="/school/:school" element={<SchoolStats />} />
          <Route path="/major" element={<MajorStats />} />
          <Route path="/major/:major" element={<MajorStats />} />
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
