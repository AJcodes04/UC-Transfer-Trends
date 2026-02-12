import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { AppShell, NavLink as MantineNavLink, Title, Group } from '@mantine/core'
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
      padding="md"
    >
      <AppShell.Navbar p="md">
        <Title order={4} mb="md">UC Transfer Trends</Title>
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
    </AppShell>
  )
}
