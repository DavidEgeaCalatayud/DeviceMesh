import type { Device } from '../../entities/device/types'
import type { MetricSample } from '../../entities/telemetry/types'

function metricValue(metrics: MetricSample[], name: string): number | null {
  return metrics.find((metric) => metric.name === name)?.value ?? null
}

function display(value: number | null, suffix: string): string {
  return value === null ? '—' : `${value.toFixed(1)}${suffix}`
}

export function DeviceList({ devices, metrics }: { devices: Device[], metrics: MetricSample[] }) {
  if (devices.length === 0) return <p className="muted">No devices discovered yet. Enroll an agent or run discovery.</p>
  return <div className="deviceList">{devices.map((device) => {
    const deviceMetrics = metrics.filter((metric) => metric.deviceId === device.id)
    const cpu = metricValue(deviceMetrics, 'host.cpu.utilization.percent')
    const memory = metricValue(deviceMetrics, 'host.memory.utilization.percent')
    const latency = metricValue(deviceMetrics, 'network.latency.ms')
    return <div className="device" key={device.id}>
      <div className="deviceIdentity"><strong>{device.hostname ?? device.id}</strong><div className="muted">{device.operatingSystem ?? 'Unknown OS'}{device.operatingSystemVersion ? ` ${device.operatingSystemVersion}` : ''} · {device.ipAddresses[0] ?? 'No IP'}</div><div className="deviceMeta">{device.manufacturer ?? device.macAddresses[0] ?? 'Identity pending'}{device.architecture ? ` · ${device.architecture}` : ''}</div></div>
      <div className="deviceMetrics"><span>CPU {display(cpu, '%')}</span><span>RAM {display(memory, '%')}</span><span>RTT {display(latency, ' ms')}</span></div>
      <div className={device.status === 'online' ? 'online' : 'offline'}>{device.status}</div>
    </div>
  })}</div>
}
