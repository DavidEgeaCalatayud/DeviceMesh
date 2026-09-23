import type { Device } from '../../entities/device/types'

export function DeviceList({ devices }: { devices: Device[] }) {
  if (devices.length === 0) return <p className="muted">No devices discovered yet. Enroll an agent or run discovery.</p>
  return <div className="deviceList">{devices.map((device) => <div className="device" key={device.id}>
    <div className="deviceIdentity"><strong>{device.hostname ?? device.id}</strong><div className="muted">{device.operatingSystem ?? 'Unknown OS'}{device.operatingSystemVersion ? ` ${device.operatingSystemVersion}` : ''} · {device.ipAddresses[0] ?? 'No IP'}</div><div className="deviceMeta">{device.manufacturer ?? device.macAddresses[0] ?? 'Identity pending'}{device.architecture ? ` · ${device.architecture}` : ''}</div></div>
    <div className={device.status === 'online' ? 'online' : 'offline'}>{device.status}</div>
  </div>)}</div>
}
