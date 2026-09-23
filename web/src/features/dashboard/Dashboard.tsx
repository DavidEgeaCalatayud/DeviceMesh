import { useEffect, useMemo, useState } from 'react'
import type { Device } from '../../entities/device/types'
import type { DeviceEvent } from '../../entities/event/types'
import type { MetricSample } from '../../entities/telemetry/types'
import { listDevices, listEvents, listLatestTelemetry } from '../../shared/api/client'
import { connectEventStream, isDeviceEventEnvelope } from '../../shared/websocket/eventStream'
import { DeviceList } from '../devices/DeviceList'
import { EventTimeline } from '../events/EventTimeline'

function isAbortError(reason: unknown): boolean {
  return reason instanceof DOMException && reason.name === 'AbortError'
}

export function Dashboard() {
  const [devices, setDevices] = useState<Device[]>([])
  const [events, setEvents] = useState<DeviceEvent[]>([])
  const [metrics, setMetrics] = useState<MetricSample[]>([])
  const [error, setError] = useState<string | null>(null)

  const applySnapshot = (nextDevices: Device[], nextEvents: DeviceEvent[], nextMetrics: MetricSample[]) => {
    setDevices(nextDevices)
    setEvents(nextEvents)
    setMetrics(nextMetrics)
    setError(null)
  }

  const refresh = async () => {
    try {
      const [nextDevices, nextEvents, nextMetrics] = await Promise.all([
        listDevices(),
        listEvents(),
        listLatestTelemetry(),
      ])
      applySnapshot(nextDevices, nextEvents, nextMetrics)
    } catch (reason) {
      setError(String(reason))
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      listDevices(controller.signal),
      listEvents(controller.signal),
      listLatestTelemetry(controller.signal),
    ])
      .then(([nextDevices, nextEvents, nextMetrics]) => {
        applySnapshot(nextDevices, nextEvents, nextMetrics)
      })
      .catch((reason: unknown) => {
        if (!isAbortError(reason)) setError(String(reason))
      })
    return () => controller.abort()
  }, [])

  useEffect(() => connectEventStream((envelope) => {
    if (!isDeviceEventEnvelope(envelope)) return
    setEvents((current) => [envelope.payload, ...current].slice(0, 100))
    void listDevices().then(setDevices).catch((reason: unknown) => setError(String(reason)))
  }), [])

  const online = useMemo(() => devices.filter((device) => device.status === 'online').length, [devices])

  return <main className="shell">
    <section className="hero">
      <div><div className="eyebrow">Local-first device observability</div><h1>DeviceMesh</h1><p>Discover, identify and monitor the devices that make up your network.</p></div>
      <div className="status">V1 realtime</div>
    </section>
    <section className="grid">
      <article className="card"><div className="muted">Known devices</div><div className="metric">{devices.length}</div></article>
      <article className="card"><div className="muted">Online</div><div className="metric">{online}</div></article>
      <article className="card"><div className="muted">Recent events</div><div className="metric">{events.length}</div></article>
      <article className="card"><div className="muted">Live metrics</div><div className="metric">{metrics.length}</div></article>
    </section>
    {error && <section className="errorBanner">{error}</section>}
    <section className="contentGrid">
      <article className="card panel">
        <div className="panelHeader"><div><div className="eyebrow">Inventory</div><h2>Devices</h2></div><button onClick={() => void refresh()}>Refresh</button></div>
        <DeviceList devices={devices} metrics={metrics} />
      </article>
      <article className="card panel"><div className="eyebrow">Network history</div><h2>Timeline</h2><EventTimeline events={events} /></article>
    </section>
  </main>
}
