import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import type {
  ServiceConsensus,
  ServiceIncidentSummary,
  SyntheticMonitor,
  SyntheticMonitorKind,
  SyntheticProbe,
  SyntheticProbeAssignment,
} from '../../entities/synthetic/types'
import {
  assignSyntheticProbe,
  createSyntheticProbe,
  getServiceConsensus,
  getServiceIncidents,
  listSyntheticProbeAssignments,
  listSyntheticProbes,
  setSyntheticProbeAssignmentEnabled,
  setSyntheticProbeEnabled,
} from '../../shared/api/syntheticOperations'

interface DistributedSyntheticsPanelProps {
  token: string
  monitors: SyntheticMonitor[]
}

function consensusLabel(consensus: ServiceConsensus | undefined): string {
  if (!consensus) return 'No observations yet'
  if (consensus.classification === 'healthy') return 'Healthy from all active probes'
  if (consensus.classification === 'global_outage') return 'Probable service outage'
  if (consensus.classification === 'regional_degradation') return 'Regional / path degradation'
  return 'Insufficient distributed data'
}

function durationLabel(seconds: number | null): string {
  if (seconds == null) return '—'
  if (seconds < 60) return `${seconds.toFixed(0)} s`
  if (seconds < 3600) return `${(seconds / 60).toFixed(1)} min`
  return `${(seconds / 3600).toFixed(1)} h`
}

export function DistributedSyntheticsPanel({ token, monitors }: DistributedSyntheticsPanelProps) {
  const [probes, setProbes] = useState<SyntheticProbe[]>([])
  const [assignments, setAssignments] = useState<SyntheticProbeAssignment[]>([])
  const [consensus, setConsensus] = useState<Record<string, ServiceConsensus>>({})
  const [incidents, setIncidents] = useState<Record<string, ServiceIncidentSummary>>({})
  const [error, setError] = useState<string | null>(null)
  const [probeName, setProbeName] = useState('')
  const [probeLocation, setProbeLocation] = useState('Murcia')
  const [httpCapability, setHttpCapability] = useState(true)
  const [tcpCapability, setTcpCapability] = useState(true)
  const [icmpCapability, setIcmpCapability] = useState(false)
  const [newProbeToken, setNewProbeToken] = useState<string | null>(null)
  const [monitorId, setMonitorId] = useState('')
  const [probeId, setProbeId] = useState('')

  const selectedMonitor = useMemo(
    () => monitors.find((monitor) => monitor.id === monitorId),
    [monitors, monitorId],
  )
  const compatibleProbes = useMemo(
    () => probes.filter((probe) => !selectedMonitor || probe.capabilities.includes(selectedMonitor.kind)),
    [probes, selectedMonitor],
  )

  const refresh = async () => {
    const publicEntries = await Promise.all(
      monitors.map(async (monitor) => {
        const [nextConsensus, nextIncidents] = await Promise.all([
          getServiceConsensus(monitor.id),
          getServiceIncidents(monitor.id),
        ])
        return [monitor.id, nextConsensus, nextIncidents] as const
      }),
    )
    setConsensus(Object.fromEntries(publicEntries.map(([id, value]) => [id, value])))
    setIncidents(Object.fromEntries(publicEntries.map(([id, , value]) => [id, value])))

    if (token) {
      const [nextProbes, nextAssignments] = await Promise.all([
        listSyntheticProbes(token),
        listSyntheticProbeAssignments(token),
      ])
      setProbes(nextProbes)
      setAssignments(nextAssignments)
      setMonitorId((current) => current || monitors[0]?.id || '')
      setProbeId((current) => current || nextProbes[0]?.id || '')
    } else {
      setProbes([])
      setAssignments([])
    }
  }

  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const publicEntries = await Promise.all(
          monitors.map(async (monitor) => {
            const [nextConsensus, nextIncidents] = await Promise.all([
              getServiceConsensus(monitor.id),
              getServiceIncidents(monitor.id),
            ])
            return [monitor.id, nextConsensus, nextIncidents] as const
          }),
        )
        let nextProbes: SyntheticProbe[] = []
        let nextAssignments: SyntheticProbeAssignment[] = []
        if (token) {
          ;[nextProbes, nextAssignments] = await Promise.all([
            listSyntheticProbes(token),
            listSyntheticProbeAssignments(token),
          ])
        }
        if (!active) return
        setConsensus(Object.fromEntries(publicEntries.map(([id, value]) => [id, value])))
        setIncidents(Object.fromEntries(publicEntries.map(([id, , value]) => [id, value])))
        setProbes(nextProbes)
        setAssignments(nextAssignments)
        setMonitorId((current) => current || monitors[0]?.id || '')
        setProbeId((current) => current || nextProbes[0]?.id || '')
        setError(null)
      } catch (reason) {
        if (active) setError(String(reason))
      }
    }
    void load()
    return () => { active = false }
  }, [token, monitors])

  const submitProbe = async (event: FormEvent) => {
    event.preventDefault()
    const capabilities: SyntheticMonitorKind[] = []
    if (httpCapability) capabilities.push('http')
    if (tcpCapability) capabilities.push('tcp')
    if (icmpCapability) capabilities.push('icmp')
    try {
      const registration = await createSyntheticProbe(token, {
        name: probeName || `${probeLocation} probe`,
        location: probeLocation,
        capabilities,
      })
      setNewProbeToken(registration.token)
      setProbeName('')
      await refresh()
      setProbeId(registration.probe.id)
      setError(null)
    } catch (reason) {
      setError(String(reason))
    }
  }

  const submitAssignment = async () => {
    if (!monitorId || !probeId) return
    try {
      await assignSyntheticProbe(token, monitorId, probeId)
      await refresh()
      setError(null)
    } catch (reason) {
      setError(String(reason))
    }
  }

  return <section className="card panel distributedSynthetics">
    <div className="panelHeader">
      <div>
        <div className="eyebrow">V1.3 distributed observability</div>
        <h2>Distributed probes & service incidents</h2>
        <p className="muted">Independent vantage points distinguish a service outage from a regional or network-path failure.</p>
      </div>
      <button type="button" onClick={() => void refresh()}>Refresh distributed state</button>
    </div>

    {error && <div className="errorBanner">{error}</div>}

    <div className="contentGrid">
      <form onSubmit={submitProbe}>
        <div className="eyebrow">Probe fleet</div>
        <h3>Register probe</h3>
        <label>Name<input value={probeName} onChange={(event) => setProbeName(event.target.value)} placeholder="murcia-edge-01" /></label>
        <label>Location<input value={probeLocation} onChange={(event) => setProbeLocation(event.target.value)} placeholder="Murcia" /></label>
        <div className="operatorRow">
          <label><input type="checkbox" checked={httpCapability} onChange={(event) => setHttpCapability(event.target.checked)} /> HTTP</label>
          <label><input type="checkbox" checked={tcpCapability} onChange={(event) => setTcpCapability(event.target.checked)} /> TCP</label>
          <label><input type="checkbox" checked={icmpCapability} onChange={(event) => setIcmpCapability(event.target.checked)} /> ICMP</label>
        </div>
        <button type="submit" disabled={!token || (!httpCapability && !tcpCapability && !icmpCapability)}>Create probe</button>
        {newProbeToken && <div className="compactItem"><div><strong>One-time probe token</strong><span>Store it as DEVICEMESH_PROBE_TOKEN. DeviceMesh stores only its hash.</span></div><code>{newProbeToken}</code></div>}
      </form>

      <div>
        <div className="eyebrow">Scheduling</div>
        <h3>Assign vantage point</h3>
        <label>Monitor<select value={monitorId} onChange={(event) => setMonitorId(event.target.value)}><option value="">Select monitor</option>{monitors.map((monitor) => <option key={monitor.id} value={monitor.id}>{monitor.name} · {monitor.kind.toUpperCase()}</option>)}</select></label>
        <label>Probe<select value={probeId} onChange={(event) => setProbeId(event.target.value)}><option value="">Select compatible probe</option>{compatibleProbes.map((probe) => <option key={probe.id} value={probe.id}>{probe.location} · {probe.name}</option>)}</select></label>
        <button type="button" disabled={!token || !monitorId || !probeId} onClick={() => void submitAssignment()}>Assign probe</button>
        <p className="muted">Each assignment owns an independent schedule. A live remote probe suppresses the backend fallback for that monitor; if all assigned probes go stale, local monitoring resumes.</p>
      </div>
    </div>

    <div className="compactList">
      {probes.map((probe) => <div key={probe.id} className="compactItem">
        <div><strong>{probe.location} · {probe.name}</strong><span>{probe.capabilities.map((value) => value.toUpperCase()).join(' / ')} · {probe.lastSeenAt ? `last seen ${new Date(probe.lastSeenAt).toLocaleString()}` : 'never seen'}</span></div>
        <div><strong>{probe.online ? 'ONLINE' : 'OFFLINE'}</strong><span>{probe.enabled ? 'Scheduling enabled' : 'Disabled'}</span></div>
        <button type="button" disabled={!token} onClick={() => void setSyntheticProbeEnabled(token, probe.id, !probe.enabled).then(refresh).catch((reason: unknown) => setError(String(reason)))}>{probe.enabled ? 'Disable' : 'Enable'}</button>
      </div>)}
    </div>

    <div className="compactList">
      {assignments.map((assignment) => {
        const monitor = monitors.find((item) => item.id === assignment.monitorId)
        const probe = probes.find((item) => item.id === assignment.probeId)
        return <div key={`${assignment.monitorId}:${assignment.probeId}`} className="compactItem">
          <div><strong>{monitor?.name ?? assignment.monitorId}</strong><span>{probe ? `${probe.location} · ${probe.name}` : assignment.probeId}</span></div>
          <div><strong>{assignment.enabled ? 'Assigned' : 'Paused'}</strong><span>next {new Date(assignment.nextRunAt).toLocaleString()}</span></div>
          <button type="button" disabled={!token} onClick={() => void setSyntheticProbeAssignmentEnabled(token, assignment.monitorId, assignment.probeId, !assignment.enabled).then(refresh).catch((reason: unknown) => setError(String(reason)))}>{assignment.enabled ? 'Pause' : 'Resume'}</button>
        </div>
      })}
    </div>

    <div className="compactList syntheticList">
      {monitors.map((monitor) => {
        const serviceConsensus = consensus[monitor.id]
        const incidentSummary = incidents[monitor.id]
        const openIncident = incidentSummary?.openIncident
        return <div key={monitor.id} className="compactItem">
          <div>
            <strong>{monitor.name}</strong>
            <span>{consensusLabel(serviceConsensus)} · {serviceConsensus?.healthyProbes ?? 0} up / {serviceConsensus?.failingProbes ?? 0} down</span>
            {serviceConsensus?.states.map((state) => <span key={state.probeId}>{state.location}: {state.success ? 'UP' : 'DOWN'} · {state.latencyMs.toFixed(0)} ms</span>)}
          </div>
          <div>
            <strong>{openIncident ? `${openIncident.classification} · OPEN` : 'No open incident'}</strong>
            <span>threshold {monitor.failureThreshold} fail / {monitor.recoveryThreshold} recover</span>
            <span>MTTR {durationLabel(incidentSummary?.meanRecoverySeconds ?? null)} · {incidentSummary?.resolvedCount ?? 0} resolved</span>
            {openIncident?.maintenanceActiveAtOpen && <span>Opened during maintenance</span>}
            {openIncident?.hostOfflineAtOpen && <span>Host was offline when incident opened</span>}
          </div>
        </div>
      })}
    </div>
  </section>
}
