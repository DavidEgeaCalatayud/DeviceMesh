import { useEffect, useState } from 'react'
import { Dashboard } from '../features/dashboard/Dashboard'
import { DeviceDetailPage } from '../features/devices/DeviceDetailPage'
import './platform.css'
import './global-search.css'
import { AdministrationPage, IncidentsPage, ServicesPage } from '../features/platform/PlatformPages'
import { AccountSecurityPage } from '../features/platform/AccountSecurityPage'
import { AuditPage } from '../features/platform/AuditPage'
import { EcosystemPage } from '../features/platform/EcosystemPage'
import { GlobalSearch } from '../features/platform/GlobalSearch'
import { SecureLoginPage } from '../features/platform/SecureLoginPage'
import { WorkspacePreferencesPage } from '../features/platform/WorkspacePreferencesPage'
import { getToken, signOut } from '../shared/api/session'
import { navigationCopy, useWorkspacePreferences } from '../shared/preferences'
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
  const preferences = useWorkspacePreferences()
  const nav = navigationCopy(preferences.locale)

  useEffect(() => {
    document.documentElement.lang = preferences.locale
  }, [preferences.locale])

  useEffect(() => {
    if (hash && hash !== '#/preferences' && hash !== '#/login' && hash !== '#/security') {
      sessionStorage.setItem('devicemesh.lastWorkspaceRoute', hash)
    }
  }, [hash])

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
  if (hash === '#/audit') page = <AuditPage />
  if (hash === '#/ecosystem') page = <EcosystemPage />
  if (hash === '#/preferences') page = <WorkspacePreferencesPage />
  if (hash === '#/security') page = <AccountSecurityPage />
  return <><nav className="platform-nav" aria-label={preferences.locale === 'es' ? 'Navegación principal' : 'Main navigation'}>
    <a href="#/">{nav.overview}</a><a href="#/services">{nav.services}</a><a href="#/incidents">{nav.incidents}</a>
    <a href="#/maintenance">{nav.maintenance}</a><a href="#/operations">{nav.operations}</a>
    <a href="#/synthetics">{nav.synthetics}</a><a href="#/probes">{nav.probes}</a>
    <a href="#/administration">{nav.administration}</a><a href="#/audit">{nav.audit}</a>
    <a href="#/ecosystem">{nav.ecosystem}</a>
    <a href="#/preferences">{nav.preferences}</a>
    {getToken() && <a href="#/security">{nav.security}</a>}
    <GlobalSearch />
    {getToken() ? <button onClick={() => void signOut()}>{nav.signOut}</button> : <a href="#/login">{nav.signIn}</a>}
  </nav>{page}</>
}
