import { useEffect, useState } from 'react'
import { Dashboard } from '../features/dashboard/Dashboard'
import { DeviceDetailPage } from '../features/devices/DeviceDetailPage'
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
  if (route.kind === 'device') return <DeviceDetailPage deviceId={route.deviceId} />
  if (route.kind === 'operator') return <OperatorConsole />
  return <Dashboard />
}
