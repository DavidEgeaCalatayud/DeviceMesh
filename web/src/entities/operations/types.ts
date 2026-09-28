export type RemoteOperationStatus = 'queued' | 'claimed' | 'succeeded' | 'failed' | 'expired'
export type RemoteOperationType =
  | 'telemetry.collect'
  | 'inventory.refresh'
  | 'agent.health_check'
  | 'network.dns_lookup'
  | 'network.route_snapshot'

export interface RemoteOperation {
  id: string
  deviceId: string
  agentId: string
  operationType: RemoteOperationType
  status: RemoteOperationStatus
  requestedBy: string
  createdAt: string
  expiresAt: string
  arguments: Record<string, unknown>
  claimedAt: string | null
  completedAt: string | null
  result: Record<string, unknown>
  error: string | null
}
