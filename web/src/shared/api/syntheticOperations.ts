import type {
  ServiceConsensus,
  ServiceIncidentSummary,
  SyntheticMonitorKind,
  SyntheticProbe,
  SyntheticProbeAssignment,
  SyntheticProbeRegistration,
} from '../../entities/synthetic/types'

const apiBase = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

function operatorHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
}

export async function listSyntheticProbes(token: string): Promise<SyntheticProbe[]> {
  const response = await fetch(`${apiBase}/api/v1/operator/synthetic-probes`, {
    headers: operatorHeaders(token),
  })
  if (!response.ok) throw new Error(`Synthetic probe API failed: ${response.status}`)
  return response.json() as Promise<SyntheticProbe[]>
}

export async function createSyntheticProbe(
  token: string,
  input: { name: string; location: string; capabilities: SyntheticMonitorKind[] },
): Promise<SyntheticProbeRegistration> {
  const response = await fetch(`${apiBase}/api/v1/operator/synthetic-probes`, {
    method: 'POST',
    headers: operatorHeaders(token),
    body: JSON.stringify(input),
  })
  if (!response.ok) throw new Error(`Create synthetic probe failed: ${response.status}`)
  return response.json() as Promise<SyntheticProbeRegistration>
}

export async function setSyntheticProbeEnabled(
  token: string,
  probeId: string,
  enabled: boolean,
): Promise<SyntheticProbe> {
  const response = await fetch(
    `${apiBase}/api/v1/operator/synthetic-probes/${encodeURIComponent(probeId)}/state`,
    {
      method: 'PATCH',
      headers: operatorHeaders(token),
      body: JSON.stringify({ enabled }),
    },
  )
  if (!response.ok) throw new Error(`Update synthetic probe failed: ${response.status}`)
  return response.json() as Promise<SyntheticProbe>
}

export async function listSyntheticProbeAssignments(
  token: string,
): Promise<SyntheticProbeAssignment[]> {
  const response = await fetch(`${apiBase}/api/v1/operator/synthetic-probe-assignments`, {
    headers: operatorHeaders(token),
  })
  if (!response.ok) throw new Error(`Synthetic assignment API failed: ${response.status}`)
  return response.json() as Promise<SyntheticProbeAssignment[]>
}

export async function assignSyntheticProbe(
  token: string,
  monitorId: string,
  probeId: string,
): Promise<SyntheticProbeAssignment> {
  const response = await fetch(
    `${apiBase}/api/v1/operator/synthetic-monitors/${encodeURIComponent(monitorId)}/probes/${encodeURIComponent(probeId)}`,
    { method: 'PUT', headers: operatorHeaders(token) },
  )
  if (!response.ok) throw new Error(`Assign synthetic probe failed: ${response.status}`)
  return response.json() as Promise<SyntheticProbeAssignment>
}

export async function setSyntheticProbeAssignmentEnabled(
  token: string,
  monitorId: string,
  probeId: string,
  enabled: boolean,
): Promise<SyntheticProbeAssignment> {
  const response = await fetch(
    `${apiBase}/api/v1/operator/synthetic-monitors/${encodeURIComponent(monitorId)}/probes/${encodeURIComponent(probeId)}`,
    {
      method: 'PATCH',
      headers: operatorHeaders(token),
      body: JSON.stringify({ enabled }),
    },
  )
  if (!response.ok) throw new Error(`Update synthetic assignment failed: ${response.status}`)
  return response.json() as Promise<SyntheticProbeAssignment>
}

export async function getServiceConsensus(monitorId: string): Promise<ServiceConsensus> {
  const response = await fetch(
    `${apiBase}/api/v1/synthetic-monitors/${encodeURIComponent(monitorId)}/consensus`,
  )
  if (!response.ok) throw new Error(`Service consensus API failed: ${response.status}`)
  return response.json() as Promise<ServiceConsensus>
}

export async function getServiceIncidents(monitorId: string): Promise<ServiceIncidentSummary> {
  const response = await fetch(
    `${apiBase}/api/v1/synthetic-monitors/${encodeURIComponent(monitorId)}/incidents?limit=50`,
  )
  if (!response.ok) throw new Error(`Service incident API failed: ${response.status}`)
  return response.json() as Promise<ServiceIncidentSummary>
}
