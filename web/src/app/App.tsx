import { useEffect, useState } from 'react'
import { Dashboard } from '../features/dashboard/Dashboard'
import { DeviceDetailPage } from '../features/devices/DeviceDetailPage'
import './platform.css'
import { AdministrationPage, IncidentsPage, LoginPage, ServicesPage } from '../features/platform/PlatformPages'
import { getToken, signOut } from '../shared/api/session'
import { OperatorConsole } from '../features/settings/OperatorConsole'

type Route = { kind: 'dashboard' } | { kind: 'device'; deviceId: string } | { kind: 'operator' }

function routeFromHash(hash: string): Route {
  if (hash === '#/operator') return { kind: 'operator' }
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
  if (route.kind === 'operator') page = <OperatorConsole />
  if (hash === '#/login') page = <LoginPage />
  if (hash === '#/services') page = <ServicesPage />
  if (hash === '#/incidents') page = <IncidentsPage />
  if (hash.startsWith('#/incidents/')) page = <IncidentsPage key={hash} incidentId={hash.slice(12)} />
  if (hash === '#/administration') page = <AdministrationPage />
  return <><nav className="platform-nav" aria-label="Main navigation">
    <a href="#/">Overview</a><a href="#/services">Services</a><a href="#/incidents">Incidents</a>
    <a href="#/operator">Operations & probes</a><a href="#/administration">Administration</a>
    {getToken() ? <button onClick={() => void signOut()}>Sign out</button> : <a href="#/login">Sign in</a>}
  </nav>{page}</>

}
