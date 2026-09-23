import { useEffect, useMemo, useState } from 'react'
import type { Device } from '../../entities/device/types'
import { listDevices } from '../../shared/api/client'
import { DeviceList } from '../devices/DeviceList'

function isAbortError(reason: unknown): boolean {
  return reason instanceof DOMException && reason.name === 'AbortError'
}

export function Dashboard() {
  const [devices, setDevices] = useState<Device[]>([])
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => {
    try {
      setDevices(await listDevices())
      setError(null)
    } catch (reason) {
      setError(String(reason))
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    listDevices(controller.signal)
      .then((result) => {
        setDevices(result)
        setError(null)
      })
      .catch((reason: unknown) => {
        if (!isAbortError(reason)) setError(String(reason))
      })
    return () => controller.abort()
  }, [])

  const online = useMemo(() => devices.filter((device) => device.status === 'online').length, [devices])

  return <main className="shell">
    <section className="hero">
      <div><div className="eyebrow">Local-first observability</div><h1>DeviceMesh</h1><p>Discover, identify and monitor the devices that make up your network.</p></div>
      <div className="status">Foundation · v0.1</div>
    </section>
    <section className="grid">
      <article className="card"><div className="muted">Known devices</div><div className="metric">{devices.length}</div></article>
      <article className="card"><div className="muted">Online</div><div className="metric">{online}</div></article>
      <article className="card"><div className="muted">Events</div><div className="metric">—</div></article>
      <article className="card"><div className="muted">Open alerts</div><div className="metric">—</div></article>
    </section>
    <section className="card" style={{marginTop:16}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}><div><h2>Devices</h2>{error && <p className="offline">{error}</p>}</div><button onClick={() => void refresh()}>Refresh</button></div>
      <DeviceList devices={devices} />
    </section>
  </main>
}
