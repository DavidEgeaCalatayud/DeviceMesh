import type { RemoteOperation, RemoteOperationType } from '../../entities/operations/types'
import { apiBase, apiFetch } from './session'

export async function queueRemoteOperationWithArguments(
  token: string,
  deviceId: string,
  operationType: RemoteOperationType,
  args: Record<string, unknown> = {},
): Promise<RemoteOperation> {
  const response = await apiFetch(`${apiBase}/api/v1/operator/remote-operations`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ deviceId, operationType, arguments: args, ttlSeconds: 300 }),
  })
  if (!response.ok) throw new Error(`Queue remote operation failed: ${response.status}`)
  return response.json() as Promise<RemoteOperation>
}
