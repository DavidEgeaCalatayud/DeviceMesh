import type { Device } from '../../entities/device/types'
import type { DeviceService, NetworkTopology } from '../../entities/network/types'

interface Props {
  topology: NetworkTopology
  services: DeviceService[]
  devices: Device[]
}

export function NetworkPanel({ topology, services, devices }: Props) {
  const deviceById = new Map(devices.map((device) => [device.id, device]))
  const servicesByDevice = new Map<string, DeviceService[]>()
  for (const service of services) {
    servicesByDevice.set(service.deviceId, [...(servicesByDevice.get(service.deviceId) ?? []), service])
  }

  const networks = topology.nodes.filter((node) => node.kind === 'network')
  if (networks.length === 0) {
    return <p className="muted">No observed network segments yet. Run the network probe with an authorized CIDR scope.</p>
  }

  return <div>
    <div className="topologyNotice">
      <strong>Observed topology</strong>
      <span>{topology.approximate ? 'Approximate' : 'Authoritative'} · {topology.method}</span>
    </div>
    <div className="networkSegments">
      {networks.map((network) => {
        const deviceNodes = topology.edges
          .filter((edge) => edge.source === network.id)
          .map((edge) => topology.nodes.find((node) => node.id === edge.target))
          .filter((node) => node?.kind === 'device')
        return <section className="networkSegment" key={network.id}>
          <div className="networkRoot">
            <div className="networkIcon">LAN</div>
            <div><strong>{network.label}</strong><div className="muted">{deviceNodes.length} observed device(s)</div></div>
          </div>
          <div className="networkDeviceList">
            {deviceNodes.map((node) => {
              if (!node?.deviceId) return null
              const device = deviceById.get(node.deviceId)
              const deviceServices = servicesByDevice.get(node.deviceId) ?? []
              return <div className="networkDevice" key={node.id}>
                <div className="networkBranch" aria-hidden="true">↳</div>
                <div className="networkDeviceBody">
                  <div className="networkDeviceHeading">
                    <strong>{device?.hostname ?? node.label}</strong>
                    <span className={device?.status === 'online' ? 'online' : 'offline'}>{device?.status ?? node.status ?? 'unknown'}</span>
                  </div>
                  <div className="muted">{device?.ipAddresses[0] ?? node.deviceId}</div>
                  <div className="serviceChips">
                    {deviceServices.length === 0
                      ? <span className="serviceNone">No configured TCP services observed</span>
                      : deviceServices.map((service) => <span className="serviceChip" key={`${service.transport}-${service.port}`}>
                          {service.name ?? service.transport} · {service.port}/{service.transport}
                        </span>)}
                  </div>
                </div>
              </div>
            })}
          </div>
        </section>
      })}
    </div>
  </div>
}
