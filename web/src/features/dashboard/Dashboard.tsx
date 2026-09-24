import { useEffect, useMemo, useState } from 'react'
import type { AlertIncident } from '../../entities/alert/types'
import type { Device } from '../../entities/device/types'
import type { DeviceEvent } from '../../entities/event/types'
import type { DeviceService, NetworkTopology } from '../../entities/network/types'
import type { MetricSample } from '../../entities/telemetry/types'
import {
  getNetworkTopology,
  listAlerts,
  listDevices,
  listEvents,
  listLatestTelemetry,
  listServices,
} from '../../shared/api/client'
import { connectEventStream, isDeviceEventEnvelope } from '../../shared/websocket/eventStream'
import { AlertPanel } from '../alerts/AlertPanel'
import { DeviceList } from '../devices/DeviceList'
import { EventTimeline } from '../events/EventTimeline'
import { NetworkPanel } from '../network/NetworkPanel'
import { TelemetryHistoryPanel } from '../telemetry/TelemetryHistoryPanel'

function isAbortError(reason: unknown): boolean {
  return reason instanceof DOMException && reason.name === 'AbortError'
}

const emptyTopology: NetworkTopology = {
  nodes: [],
  edges: [],
  method: 'observation-segment',
  approximate: true,
}

export function Dashboard() {
  const [devices, setDevices] = useState<Device[]>([])
  const [events, setEvents] = useState<DeviceEvent[]>([])
  const [metrics, setMetrics] = useState<MetricSample[]>([])
  const [alerts, setAlerts] = useState<AlertIncident[]>([])
  const [services, setServices] = useState<DeviceService[]>([])
  const [topology, setTopology] = useState<NetworkTopology>(emptyTopology)
  const [error, setError] = useState<string | null>(null)

  const applySnapshot = (
    nextDevices: Device[],
    nextEvents: DeviceEvent[],
    nextMetrics: MetricSample[],
    nextAlerts: AlertIncident[],
    nextServices: DeviceService[],
    nextTopology: NetworkTopology,
  ) => {
    setDevices(nextDevices)
    setEvents(nextEvents)
    setMetrics(nextMetrics)
    setAlerts(nextAlerts)
    setServices(nextServices)
    setTopology(nextTopology)
    setError(null)
  }

  const refresh = async () => {
    try {
      const [nextDevices, nextEvents, nextMetrics, nextAlerts, nextServices, nextTopology] = await Promise.all([
        listDevices(),
        listEvents(),
        listLatestTelemetry(),
        listAlerts(),
        listServices(),
        getNetworkTopology(),
      ])
      applySnapshot(nextDevices, nextEvents, nextMetrics, nextAlerts, nextServices, nextTopology)
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
      listServices(controller.signal),
      getNetworkTopology(controller.signal),
    ])
      .then(([nextDevices, nextEvents, nextMetrics, nextAlerts, nextServices, nextTopology]) => {
        applySnapshot(nextDevices, nextEvents, nextMetrics, nextAlerts, nextServices, nextTopology)
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
    if (envelope.payload.name.startsWith('SERVICE_')) {
      void listServices().then(setServices).catch((reason: unknown) => setError(String(reason)))
    }
    void Promise.all([listDevices(), getNetworkTopology()])
      .then(([nextDevices, nextTopology]) => {
        setDevices(nextDevices)
        setTopology(nextTopology)
      })
      .catch((reason: unknown) => setError(String(reason)))
  }), [])

  const online = useMemo(() => devices.filter((device) => device.status === 'online').length, [devices])
  const openAlerts = useMemo(() => alerts.filter((alert) => alert.active).length, [alerts])

  return <main className="shell">
    <section className="hero">
      <div><div className="eyebrow">Local-first device observability</div><h1>DeviceMesh</h1><p>Discover, identify and monitor the devices that make up your network.</p></div>
      <div className="heroActions"><a className="status" href="#/operator">Operator Console</a><div className="status">V1.2 service observability</div></div>
    </section>
    <section className="grid">
      <article className="card"><div className="muted">Known devices</div><div className="metric">{devices.length}</div></article>
      <article className="card"><div className="muted">Online</div><div className="metric">{online}</div></article>
      <article className="card"><div className="muted">Open services</div><div className="metric">{services.length}</div></article>
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
    <TelemetryHistoryPanel devices={devices} />
    <section className="card networkPanel">
      <div className="eyebrow">Observed network</div>
      <h2>Topology & exposed services</h2>
      <NetworkPanel topology={topology} services={services} devices={devices} />
    </section>
    <section className="card alertPanel">
      <div className="eyebrow">Incidents</div>
      <h2>Threshold alerts</h2>
      <AlertPanel alerts={alerts} devices={devices} />
    </section>
  </main>
}
