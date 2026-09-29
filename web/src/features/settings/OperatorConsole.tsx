import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import type { Device } from '../../entities/device/types'
import type { MaintenanceWindow } from '../../entities/health/types'
import type { RemoteOperation, RemoteOperationType } from '../../entities/operations/types'
import type { SyntheticHealth, SyntheticMonitor, SyntheticMonitorKind } from '../../entities/synthetic/types'
import {
  cancelMaintenanceWindow,
  createMaintenanceWindow,
  createSyntheticMonitor,
  getSyntheticHealth,
  listDevices,
  listMaintenanceWindows,
  listRemoteOperations,
  listSyntheticMonitors,
  setSyntheticMonitorEnabled,
} from '../../shared/api/client'
import { queueRemoteOperationWithArguments } from '../../shared/api/operations'
import { DistributedSyntheticsPanel } from './DistributedSyntheticsPanel'

export type OperatorSection = 'all' | 'maintenance' | 'operations' | 'synthetics' | 'probes'

const operationTypes: RemoteOperationType[] = [
  'telemetry.collect',
  'inventory.refresh',
  'agent.health_check',
  'network.dns_lookup',
  'network.route_snapshot',
]

function localDateInput(date: Date): string {
  const offset = date.getTimezoneOffset() * 60000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}

const sectionCopy: Record<OperatorSection, { eyebrow: string; title: string; description: string }> = {
  all: {
    eyebrow: 'Operations & observability',
    title: 'Operator Console',
    description: 'Maintenance, controlled remote operations, synthetic service monitoring and distributed probes.',
  },
  maintenance: {
    eyebrow: 'Noise control',
    title: 'Maintenance',
    description: 'Schedule and cancel global or device-scoped maintenance windows without hiding collected telemetry.',
  },
  operations: {
    eyebrow: 'Safe control plane',
    title: 'Remote Operations',
    description: 'Queue only declarative allowlisted operations; no arbitrary shell or process execution is exposed.',
  },
  synthetics: {
    eyebrow: 'Service health',
    title: 'Synthetic Monitoring',
    description: 'Create and operate HTTP, TCP, ICMP, DNS and TLS monitors independently from agent health.',
  },
  probes: {
    eyebrow: 'Distributed vantage points',
    title: 'Distributed Probes',
    description: 'Operate probe registration, assignments and consensus from dedicated regional vantage points.',
  },
}

export function OperatorConsole({ section = 'all' }: { section?: OperatorSection }) {
  const [token, setToken] = useState(() => sessionStorage.getItem('devicemesh.operatorToken') ?? '')
  const [devices, setDevices] = useState<Device[]>([])
  const [maintenance, setMaintenance] = useState<MaintenanceWindow[]>([])
  const [operations, setOperations] = useState<RemoteOperation[]>([])
  const [monitors, setMonitors] = useState<SyntheticMonitor[]>([])
  const [syntheticHealth, setSyntheticHealth] = useState<Record<string, SyntheticHealth>>({})
  const [error, setError] = useState<string | null>(null)
  const [deviceId, setDeviceId] = useState('')
  const [operationType, setOperationType] = useState<RemoteOperationType>('agent.health_check')
  const [dnsHostname, setDnsHostname] = useState('example.com')
  const [maintenanceReason, setMaintenanceReason] = useState('Planned maintenance')
  const [maintenanceStart, setMaintenanceStart] = useState(() => localDateInput(new Date()))
  const [maintenanceEnd, setMaintenanceEnd] = useState(() => localDateInput(new Date(Date.now() + 60 * 60 * 1000)))
  const [monitorName, setMonitorName] = useState('')
  const [monitorKind, setMonitorKind] = useState<SyntheticMonitorKind>('http')
  const [monitorTarget, setMonitorTarget] = useState('https://example.com/health')
  const [monitorPort, setMonitorPort] = useState('443')
  const [httpExpectedStatus, setHttpExpectedStatus] = useState('200')
  const [httpBodyContains, setHttpBodyContains] = useState('')
  const [httpHeaderName, setHttpHeaderName] = useState('')
  const [httpHeaderValue, setHttpHeaderValue] = useState('')
  const [httpSecretHeaderName, setHttpSecretHeaderName] = useState('')
  const [httpSecretRef, setHttpSecretRef] = useState('')

  const selectedDevice = useMemo(() => devices.find((device) => device.id === deviceId), [devices, deviceId])
  const copy = sectionCopy[section]
  const show = (target: Exclude<OperatorSection, 'all'>) => section === 'all' || section === target

  const refreshPublic = async () => {
    const [nextDevices, nextMaintenance, nextMonitors] = await Promise.all([
      listDevices(),
      listMaintenanceWindows(),
      listSyntheticMonitors(),
    ])
    const healthEntries = await Promise.all(
      nextMonitors.map(async (monitor) => [monitor.id, await getSyntheticHealth(monitor.id)] as const),
    )
    setDevices(nextDevices)
    setMaintenance(nextMaintenance)
    setMonitors(nextMonitors)
    setSyntheticHealth(Object.fromEntries(healthEntries))
    setDeviceId((current) => current || nextDevices[0]?.id || '')
  }

  const refreshOperator = async (nextToken = token) => {
    if (!nextToken) {
      setOperations([])
      return
    }
    setOperations(await listRemoteOperations(nextToken))
  }

  const refresh = async () => {
    try {
      await Promise.all([refreshPublic(), refreshOperator()])
      setError(null)
    } catch (reason) {
      setError(String(reason))
    }
  }

  useEffect(() => {
    let active = true
    const loadInitialState = async () => {
      try {
        const [nextDevices, nextMaintenance, nextMonitors] = await Promise.all([
          listDevices(),
          listMaintenanceWindows(),
          listSyntheticMonitors(),
        ])
        const healthEntries = await Promise.all(
          nextMonitors.map(async (monitor) => [monitor.id, await getSyntheticHealth(monitor.id)] as const),
        )
        if (!active) return
        setDevices(nextDevices)
        setMaintenance(nextMaintenance)
        setMonitors(nextMonitors)
        setSyntheticHealth(Object.fromEntries(healthEntries))
        setDeviceId(nextDevices[0]?.id ?? '')
      } catch (reason) {
        if (active) setError(String(reason))
      }
    }
    void loadInitialState()
    return () => { active = false }
  }, [])

  const saveToken = async () => {
    sessionStorage.setItem('devicemesh.operatorToken', token)
    try {
      await refreshOperator(token)
      setError(null)
    } catch (reason) {
      setError(String(reason))
    }
  }

  const submitMaintenance = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await createMaintenanceWindow(token, {
        deviceId: deviceId || null,
        startsAt: new Date(maintenanceStart).toISOString(),
        endsAt: new Date(maintenanceEnd).toISOString(),
        reason: maintenanceReason,
      })
      await refreshPublic()
      setError(null)
    } catch (reason) {
      setError(String(reason))
    }
  }

  const submitOperation = async () => {
    if (!deviceId) return
    try {
      const args = operationType === 'network.dns_lookup' ? { hostname: dnsHostname.trim() } : {}
      await queueRemoteOperationWithArguments(token, deviceId, operationType, args)
      await refreshOperator()
      setError(null)
    } catch (reason) {
      setError(String(reason))
    }
  }

  const submitMonitor = async (event: FormEvent) => {
    event.preventDefault()
    try {
      const usesPort = monitorKind === 'tcp' || monitorKind === 'tls'
      const isHttp = monitorKind === 'http'
      const headers = isHttp && httpHeaderName.trim()
        ? { [httpHeaderName.trim()]: httpHeaderValue }
        : {}
      const secretHeaders = isHttp && httpSecretHeaderName.trim() && httpSecretRef.trim()
        ? { [httpSecretHeaderName.trim()]: httpSecretRef.trim() }
        : {}
      await createSyntheticMonitor(token, {
        name: monitorName || `${monitorKind.toUpperCase()} ${monitorTarget}`,
        kind: monitorKind,
        target: monitorTarget,
        port: usesPort ? Number(monitorPort) : null,
        deviceId: deviceId || null,
        intervalSeconds: 60,
        timeoutSeconds: 5,
        httpMethod: isHttp ? 'GET' : null,
        expectedStatus: isHttp ? Number(httpExpectedStatus) : null,
        httpHeaders: headers,
        httpSecretHeaders: secretHeaders,
        expectedBodyContains: isHttp && httpBodyContains.trim() ? httpBodyContains : null,
      })
      await refreshPublic()
      setError(null)
    } catch (reason) {
      setError(String(reason))
    }
  }

  return <main className="shell operatorConsole">
    <section className="hero">
      <div><div className="eyebrow">{copy.eyebrow}</div><h1>{copy.title}</h1><p>{copy.description}</p></div>
      <a className="status" href="#/">Back to dashboard</a>
    </section>
    <nav className="operatorRow" aria-label="Operations navigation">
      <a href="#/maintenance">Maintenance</a>
      <a href="#/operations">Operations</a>
      <a href="#/synthetics">Synthetics</a>
      <a href="#/probes">Probes</a>
      <a href="#/operator">Combined view</a>
    </nav>
    {error && <section className="errorBanner">{error}</section>}
    <section className="card panel operatorAuth">
      <div className="panelHeader"><div><div className="eyebrow">Authorization</div><h2>Operator session</h2></div></div>
      <div className="operatorRow">
        <input aria-label="Operator bearer token" type="password" value={token} onChange={(event) => setToken(event.target.value)} placeholder="Operator bearer token" />
        <button onClick={() => void saveToken()}>Use token</button>
        <button onClick={() => void refresh()}>Refresh</button>
      </div>
      <p className="muted">The token is kept only in this browser tab via sessionStorage.</p>
    </section>
    {show('maintenance') && <form className="card panel" onSubmit={submitMaintenance}>
      <div className="eyebrow">Noise control</div><h2>Maintenance window</h2>
      <label>Device<select value={deviceId} onChange={(event) => setDeviceId(event.target.value)}><option value="">Global</option>{devices.map((device) => <option key={device.id} value={device.id}>{device.hostname ?? device.id}</option>)}</select></label>
      <label>Starts<input type="datetime-local" value={maintenanceStart} onChange={(event) => setMaintenanceStart(event.target.value)} /></label>
      <label>Ends<input type="datetime-local" value={maintenanceEnd} onChange={(event) => setMaintenanceEnd(event.target.value)} /></label>
      <label>Reason<input value={maintenanceReason} onChange={(event) => setMaintenanceReason(event.target.value)} /></label>
      <button type="submit" disabled={!token}>Schedule maintenance</button>
      <div className="compactList">{maintenance.slice(0, 20).map((window) => <div key={window.id} className="compactItem"><div><strong>{window.deviceId ?? 'Global'}</strong><span>{window.reason}</span></div><div>{window.active ? 'Active' : 'Scheduled/ended'} {window.cancelledAt ? '· Cancelled' : ''}</div>{!window.cancelledAt && <button type="button" disabled={!token} onClick={() => void cancelMaintenanceWindow(token, window.id).then(refreshPublic).catch((reason: unknown) => setError(String(reason)))}>Cancel</button>}</div>)}</div>
    </form>}
    {show('operations') && <section className="card panel">
      <div className="eyebrow">Safe control plane</div><h2>Remote operations</h2>
      <p className="muted">Only the server allowlist is exposed. Diagnostic operations remain structured and bounded.</p>
      <div className="operatorGrid">
        <label>Device<select value={deviceId} onChange={(event) => setDeviceId(event.target.value)}>{devices.map((device) => <option key={device.id} value={device.id}>{device.hostname ?? device.id}</option>)}</select></label>
        <label>Operation<select value={operationType} onChange={(event) => setOperationType(event.target.value as RemoteOperationType)}>{operationTypes.map((type) => <option key={type} value={type}>{type}</option>)}</select></label>
        {operationType === 'network.dns_lookup' && <label>Hostname<input value={dnsHostname} maxLength={253} onChange={(event) => setDnsHostname(event.target.value)} placeholder="example.com" /></label>}
      </div>
      <button disabled={!token || !deviceId || (operationType === 'network.dns_lookup' && !dnsHostname.trim())} onClick={() => void submitOperation()}>Queue operation</button>
      {selectedDevice && <p className="muted">Target: {selectedDevice.hostname ?? selectedDevice.id} · {selectedDevice.status}</p>}
      <div className="compactList">{operations.slice(0, 50).map((operation) => <div key={operation.id} className="compactItem"><div><strong>{operation.operationType}</strong><span>{operation.deviceId}</span></div><div><strong>{operation.status}</strong><span>{operation.error ?? (operation.completedAt ? new Date(operation.completedAt).toLocaleString() : 'Pending')}</span></div></div>)}</div>
    </section>}
    {show('synthetics') && <form className="card panel" onSubmit={submitMonitor}>
      <div className="eyebrow">Service health</div><h2>Synthetic monitors</h2>
      <div className="operatorGrid">
        <label>Name<input value={monitorName} onChange={(event) => setMonitorName(event.target.value)} placeholder="Public API" /></label>
        <label>Kind<select value={monitorKind} onChange={(event) => setMonitorKind(event.target.value as SyntheticMonitorKind)}><option value="http">HTTP</option><option value="tcp">TCP</option><option value="icmp">ICMP</option><option value="dns">DNS</option><option value="tls">TLS</option></select></label>
        <label>Target<input value={monitorTarget} onChange={(event) => setMonitorTarget(event.target.value)} /></label>
        {(monitorKind === 'tcp' || monitorKind === 'tls') && <label>Port<input type="number" min="1" max="65535" value={monitorPort} onChange={(event) => setMonitorPort(event.target.value)} /></label>}
        {monitorKind === 'http' && <>
          <label>Expected HTTP status<input type="number" min="100" max="599" value={httpExpectedStatus} onChange={(event) => setHttpExpectedStatus(event.target.value)} /></label>
          <label>Body contains<input maxLength={512} value={httpBodyContains} onChange={(event) => setHttpBodyContains(event.target.value)} placeholder="optional response assertion" /></label>
          <label>Plain header name<input value={httpHeaderName} onChange={(event) => setHttpHeaderName(event.target.value)} placeholder="X-Client" /></label>
          <label>Plain header value<input value={httpHeaderValue} onChange={(event) => setHttpHeaderValue(event.target.value)} placeholder="DeviceMesh" /></label>
          <label>Secret header name<input value={httpSecretHeaderName} onChange={(event) => setHttpSecretHeaderName(event.target.value)} placeholder="Authorization" /></label>
          <label>Secret reference<input value={httpSecretRef} onChange={(event) => setHttpSecretRef(event.target.value)} placeholder="payments-api-token" /></label>
        </>}
      </div>
      {monitorKind === 'http' && <p className="muted">Secret fields contain references only. The actual value must be provisioned on each executing backend/probe and is never sent by this UI.</p>}
      <button type="submit" disabled={!token}>Create monitor</button>
      <div className="compactList syntheticList">{monitors.map((monitor) => {
        const health = syntheticHealth[monitor.id]
        const day = health?.windows.find((window) => window.label === '24h')
        return <div key={monitor.id} className="compactItem"><div><strong>{monitor.name}</strong><span>{monitor.kind.toUpperCase()} · {monitor.target}{monitor.port ? `:${monitor.port}` : ''}{monitor.expectedBodyContains ? ' · body assertion' : ''}{Object.keys(monitor.httpSecretHeaders).length ? ` · ${Object.keys(monitor.httpSecretHeaders).length} secret ref(s)` : ''}</span></div><div><strong>{day?.availabilityPercent == null ? 'No SLA yet' : `${day.availabilityPercent.toFixed(2)}% / 24h`}</strong><span>{day?.meanLatencyMs == null ? 'No latency yet' : `${day.meanLatencyMs.toFixed(0)} ms avg · ${day.p95LatencyMs?.toFixed(0) ?? '—'} ms p95`}</span></div><button type="button" disabled={!token} onClick={() => void setSyntheticMonitorEnabled(token, monitor.id, !monitor.enabled).then(refreshPublic).catch((reason: unknown) => setError(String(reason)))}>{monitor.enabled ? 'Disable' : 'Enable'}</button></div>
      })}</div>
    </form>}
    {show('probes') && <DistributedSyntheticsPanel token={token} monitors={monitors} />}
  </main>
}
