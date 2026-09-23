export type ServiceState = 'open' | 'closed'

export interface DeviceService {
  deviceId: string
  port: number
  transport: string
  name: string | null
  state: ServiceState
  firstSeen: string
  lastSeen: string
  lastChangedAt: string
  source: string
  networkCidr: string | null
}

export interface TopologyNode {
  id: string
  kind: 'network' | 'device'
  label: string
  deviceId: string | null
  networkCidr: string | null
  status: string | null
}

export interface TopologyEdge {
  source: string
  target: string
  relation: string
}

export interface NetworkTopology {
  nodes: TopologyNode[]
  edges: TopologyEdge[]
  method: string
  approximate: boolean
}
