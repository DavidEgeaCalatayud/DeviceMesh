import { useEffect, useMemo, useState } from 'react'
import type { AlertIncident } from '../../entities/alert/types'
import type { Device } from '../../entities/device/types'
import type { DeviceEvent } from '../../entities/event/types'
import type { MetricSample } from '../../entities/telemetry/types'
import { listAlerts, listDevices, listEvents, listLatestTelemetry } from '../../shared/api/client'
import { connectEventStream, isDeviceEventEnvelope } from '../../shared/websocket/eventStream'
import { AlertPanel } from '../alerts/AlertPanel'
import { DeviceList } from '../devices/DeviceList'
import { EventTimeline } from '../events/EventTimeline'

function isAbortError(reason: unknown): boolean {
  return reason instanceof DOMException && reason.name === 'AbortError'
}

export function Dashboard() {
  const [devices, setDevices] = useState<Device[]>([])
  const [events, setEvents] = useState<DeviceEvent[]>([])
  const [metrics, setMetrics] = useState<MetricSample[]>([])
  const [alerts, setAlerts] = useState<AlertIncident[]>([])
  const [error, setError] = useState<string | null>(null)

  const applySnapshot = (
    nextDevices: Device[],
    nextEvents: DeviceEvent[],
    nextMetrics: MetricSample[],
    nextAlerts: AlertIncident[],
  ) => {
    setDevices(nextDevices)
    setEvents(nextEvents)
    setMetrics(nextMetrics)
    setAlerts(nextAlerts)
    setError(null)
  }

  const refresh = async () => {
    try {
      const [nextDevices, nextEvents, nextMetrics, nextAlerts] = await Promise.all([
        listDevices(),
        listEvents(),
        listLatestTelemetry(),
        listAlerts(),
      ])
      applySnapshot(nextDevices, nextEvents, nextMetrics, nextAlerts)
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
      listAlerts(controller.signal),
    ])
      .then(([nextDevices, nextEvents, nextMetrics, nextAlerts]) => {
        applySnapshot(nextDevices, nextEvents, nextMetrics, nextAlerts)
      })
      .catch((reason: unknown) => {
        if (!isAbortError(reason)) setError(String(reason))
      })
    return () => controller.abort()
  }, [])

  useEffect(() => connectEventStream((envelope) => {
    if (!isDeviceEventEnvelope(envelope)) return
    setEvents((current) => [envelope.payload, ...current].slice(0, 100))
    if (envelope.payload.name.startsWith('ALERT_')) {
      void listAlerts().then(setAlerts).catch((reason: unknown) => setError(String(reason)))
      return
    }
    void listDevices().then(setDevices).catch((reason: unknown) => setError(String(reason)))
  }), [])

  const online = useMemo(() => devices.filter((device) => device.status === 'online').length, [devices])
  const openAlerts = useMemo(() => alerts.filter((alert) => alert.active).length, [alerts])

  return <main className="shell">
    <section className="hero">
      <div><div className="eyebrow">Local-first device observability</div><h1>DeviceMesh</h1><p>Discover, identify and monitor the devices that make up your network.</p></div>
      <div className="status">V1 realtime</div>
    </section>
    <section className="grid">
      <article className="card"><div className="muted">Known devices</div><div className="metric">{devices.length}</div></article>
      <article className="card"><div className="muted">Online</div><div className="metric">{online}</div></article>
      <article className="card"><div className="muted">Open alerts</div><div className="metric">{openAlerts}</div></article>
      <article className="card"><div className="muted">Recent events</div><div className="metric">{events.length}</div></article>
    </section>
    {error && <section className="errorBanner">{error}</section>}
    <section className="contentGrid">
      <article className="card panel">
        <div className="panelHeader"><div><div className="eyebrow">Inventory</div><h2>Devices</h2></div><button onClick={() => void refresh()}>Refresh</button></div>
        <DeviceList devices={devices} metrics={metrics} />
      </article>
      <article className="card panel"><div className="eyebrow">Network history</div><h2>Timeline</h2><EventTimeline events={events} /></article>
    </section>
    <section className="card alertPanel">
      <div className="eyebrow">Incidents</div>
      <h2>Threshold alerts</h2>
      <AlertPanel alerts={alerts} devices={devices} />
    </section>
  </main>
}
