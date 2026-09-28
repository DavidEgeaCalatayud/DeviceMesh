import { useEffect, useState } from 'react'
import { Dashboard } from '../features/dashboard/Dashboard'
import { DeviceDetailPage } from '../features/devices/DeviceDetailPage'
import './platform.css'
import './global-search.css'
import { AdministrationPage, IncidentsPage, ServicesPage } from '../features/platform/PlatformPages'
import { AccountSecurityPage } from '../features/platform/AccountSecurityPage'
import { AuditPage } from '../features/platform/AuditPage'
import { GlobalSearch } from '../features/platform/GlobalSearch'
import { SecureLoginPage } from '../features/platform/SecureLoginPage'
import { getToken, signOut } from '../shared/api/session'
import { OperatorConsole } from '../features/settings/OperatorConsole'
import type { OperatorSection } from '../features/settings/OperatorConsole'

type Route =
  | { kind: 'dashboard' }
  | { kind: 'device'; deviceId: string }
  | { kind: 'operator'; section: OperatorSection }

function routeFromHash(hash: string): Route {
  const operatorRoutes: Record<string, OperatorSection> = {
    '#/operator': 'all',
    '#/maintenance': 'maintenance',
    '#/operations': 'operations',
    '#/synthetics': 'synthetics',
    '#/probes': 'probes',
  }
  const section = operatorRoutes[hash]
  if (section) return { kind: 'operator', section }
  const match = hash.match(/^#\/devices\/(.+)$/)
  if (!match) return { kind: 'dashboard' }
  try {
    return { kind: 'device', deviceId: decodeURIComponent(match[1]) }
  } catch {
    return { kind: 'dashboard' }
  }
}

export function App() {
  const [hash, setHash] = useState(() => window.location.hash)

  useEffect(() => {
    const onHashChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const route = routeFromHash(hash)
  let page = <Dashboard />
  if (route.kind === 'device') page = <DeviceDetailPage deviceId={route.deviceId} />
  if (route.kind === 'operator') page = <OperatorConsole section={route.section} />
  if (hash === '#/login') page = <SecureLoginPage />
  if (hash === '#/services') page = <ServicesPage />
  if (hash === '#/incidents') page = <IncidentsPage />
  if (hash.startsWith('#/incidents/')) page = <IncidentsPage key={hash} incidentId={hash.slice(12)} />
  if (hash === '#/administration') page = <AdministrationPage />
  if (hash === '#/security') page = <AccountSecurityPage />
  if (hash === '#/audit') page = <AuditPage />
  return <><nav className="platform-nav" aria-label="Main navigation">
    <a href="#/">Overview</a><a href="#/services">Services</a><a href="#/incidents">Incidents</a>
    <a href="#/maintenance">Maintenance</a><a href="#/operations">Operations</a>
    <a href="#/synthetics">Synthetics</a><a href="#/probes">Probes</a>
    <a href="#/administration">Administration</a><a href="#/audit">Audit</a>
    {getToken() && <a href="#/security">Account security</a>}
    <GlobalSearch />
    {getToken() ? <button onClick={() => void signOut()}>Sign out</button> : <a href="#/login">Sign in</a>}
  </nav>{page}</>
}
