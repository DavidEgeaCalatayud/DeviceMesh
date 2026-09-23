import { useEffect, useMemo, useState } from 'react'
import type { AlertIncident } from '../../entities/alert/types'
import type { Device } from '../../entities/device/types'
import type { DeviceEvent } from '../../entities/event/types'
import type { DeviceService } from '../../entities/network/types'
import type { MetricSample } from '../../entities/telemetry/types'
import {
  listAlerts,
  listDevices,
  listEvents,
  listLatestTelemetry,
  listServices,
} from '../../shared/api/client'
import { AlertPanel } from '../alerts/AlertPanel'
import { EventTimeline } from '../events/EventTimeline'
import { TelemetryHistoryPanel } from '../telemetry/TelemetryHistoryPanel'

function metric(metrics: MetricSample[], name: string): MetricSample | undefined {
  return metrics.find((item) => item.name === name)
}

function formatMetric(sample: MetricSample | undefined): string {
  if (!sample) return '—'
  if (sample.unit === 'percent') return `${sample.value.toFixed(1)}%`
  if (sample.unit === 'ms') return `${sample.value.toFixed(1)} ms`
  if (sample.unit === 'seconds') return formatDuration(sample.value)
  if (sample.unit === 'bytes') return formatBytes(sample.value)
  return sample.unit ? `${sample.value.toFixed(1)} ${sample.unit}` : sample.value.toFixed(1)
}

function formatDuration(seconds: number): string {
  const wholeSeconds = Math.max(0, Math.floor(seconds))
  const days = Math.floor(wholeSeconds / 86400)
  const hours = Math.floor((wholeSeconds % 86400) / 3600)
  const minutes = Math.floor((wholeSeconds % 3600) / 60)
  if (days > 0) return `${days}d ${hours}h`
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m`
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes.toFixed(0)} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let value = bytes / 1024
  let index = 0
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024
    index += 1
  }
  return `${value.toFixed(value >= 100 ? 0 : 1)} ${units[index]}`
}

function metricCard(label: string, sample: MetricSample | undefined, hint?: string) {
  return <article className="card detailMetric" key={label}>
    <div className="muted">{label}</div>
    <div className="detailMetricValue">{formatMetric(sample)}</div>
    {hint && <div className="deviceMeta">{hint}</div>}
  </article>
}

export function DeviceOverview({
  device,
  metrics,
  services,
  alerts,
  events,
}: {
  device: Device
  metrics: MetricSample[]
  services: DeviceService[]
  alerts: AlertIncident[]
  events: DeviceEvent[]
}) {
  const deviceMetrics = metrics.filter((item) => item.deviceId === device.id)
  const activeAlerts = alerts.filter((alert) => alert.deviceId === device.id)
  const deviceEvents = events.filter((event) => event.deviceId === device.id)

  const cpu = metric(deviceMetrics, 'host.cpu.utilization.percent')
  const memory = metric(deviceMetrics, 'host.memory.utilization.percent')
  const disk = metric(deviceMetrics, 'host.disk.utilization.percent')
  const uptime = metric(deviceMetrics, 'host.uptime.seconds')
  const latency = metric(deviceMetrics, 'network.latency.ms')
  const jitter = metric(deviceMetrics, 'network.jitter.ms')
  const packetLoss = metric(deviceMetrics, 'network.packet_loss.percent')

  return <>
    <section className="detailHero">
      <div>
        <a className="backLink" href="#">← Dashboard</a>
        <div className="eyebrow">Device observability</div>
        <h1>{device.hostname ?? device.id}</h1>
        <p>{device.operatingSystem ?? 'Unknown operating system'}{device.operatingSystemVersion ? ` ${device.operatingSystemVersion}` : ''}{device.architecture ? ` · ${device.architecture}` : ''}</p>
      </div>
      <span className={`detailStatus ${device.status === 'online' ? 'online' : 'offline'}`}>{device.status}</span>
    </section>

    <section className="detailMetricGrid">
      {metricCard('CPU', cpu)}
      {metricCard('Memory', memory)}
      {metricCard('Disk', disk)}
      {metricCard('Uptime', uptime)}
      {metricCard('Latency', latency, 'Probe RTT')}
      {metricCard('Jitter', jitter, 'Mean RTT delta')}
      {metricCard('Packet loss', packetLoss, 'Probe window')}
    </section>

    <section className="detailColumns">
      <article className="card detailPanel">
        <div className="eyebrow">Identity</div>
        <h2>Network & host identity</h2>
        <dl className="identityGrid">
          <div><dt>Device ID</dt><dd>{device.id}</dd></div>
          <div><dt>Manufacturer</dt><dd>{device.manufacturer ?? 'Unknown'}</dd></div>
          <div><dt>First seen</dt><dd>{new Date(device.firstSeen).toLocaleString()}</dd></div>
          <div><dt>Last seen</dt><dd>{new Date(device.lastSeen).toLocaleString()}</dd></div>
        </dl>
        <div className="identityGroup"><strong>IP addresses</strong><div className="identityChips">{device.ipAddresses.length ? device.ipAddresses.map((value) => <span key={value}>{value}</span>) : <span>None observed</span>}</div></div>
        <div className="identityGroup"><strong>MAC addresses</strong><div className="identityChips">{device.macAddresses.length ? device.macAddresses.map((value) => <span key={value}>{value}</span>) : <span>None observed</span>}</div></div>
      </article>

      <article className="card detailPanel">
        <div className="eyebrow">Exposure</div>
        <h2>Observed services</h2>
        {services.length === 0 ? <p className="muted">No open service from the configured TCP allowlist is currently observed.</p> : <div className="detailServiceList">
          {services.map((service) => <div className="detailService" key={`${service.transport}-${service.port}`}>
            <div><strong>{service.name ?? 'unknown'}</strong><div className="deviceMeta">{service.port}/{service.transport}{service.networkCidr ? ` · ${service.networkCidr}` : ''}</div></div>
            <span className="online">{service.state}</span>
          </div>)}
        </div>}
      </article>
    </section>

    <section className="detailColumns">
      <article className="card detailPanel">
        <div className="eyebrow">Incidents</div>
        <h2>Device alerts</h2>
        <AlertPanel alerts={activeAlerts} devices={[device]} />
      </article>
      <article className="card detailPanel">
        <div className="eyebrow">Lifecycle</div>
        <h2>Device timeline</h2>
        <EventTimeline events={deviceEvents} />
      </article>
    </section>
  </>
}

export function DeviceDetailPage({ deviceId }: { deviceId: string }) {
  const [devices, setDevices] = useState<Device[]>([])
  const [metrics, setMetrics] = useState<MetricSample[]>([])
  const [alerts, setAlerts] = useState<AlertIncident[]>([])
  const [services, setServices] = useState<DeviceService[]>([])
  const [events, setEvents] = useState<DeviceEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    void Promise.all([
      listDevices(controller.signal),
      listLatestTelemetry(controller.signal),
      listAlerts(controller.signal),
      listServices(controller.signal, deviceId),
      listEvents(controller.signal, 200),
    ])
      .then(([nextDevices, nextMetrics, nextAlerts, nextServices, nextEvents]) => {
        setDevices(nextDevices)
        setMetrics(nextMetrics)
        setAlerts(nextAlerts)
        setServices(nextServices)
        setEvents(nextEvents)
        setError(null)
      })
      .catch((reason: unknown) => {
        if (!(reason instanceof DOMException && reason.name === 'AbortError')) setError(String(reason))
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [deviceId])

  const device = useMemo(() => devices.find((item) => item.id === deviceId), [deviceId, devices])

  if (loading) return <main className="shell"><div className="card">Loading device observability…</div></main>
  if (error) return <main className="shell"><a className="backLink" href="#">← Dashboard</a><div className="errorBanner">{error}</div></main>
  if (!device) return <main className="shell"><a className="backLink" href="#">← Dashboard</a><div className="card"><h2>Device not found</h2><p className="muted">The device may have been removed or its identity may have converged into another record.</p></div></main>

  return <main className="shell deviceDetailShell">
    <DeviceOverview device={device} metrics={metrics} services={services} alerts={alerts} events={events} />
    <TelemetryHistoryPanel devices={[device]} />
  </main>
}
