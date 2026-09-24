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
  queueRemoteOperation,
  setSyntheticMonitorEnabled,
} from '../../shared/api/client'
import { DistributedSyntheticsPanel } from './DistributedSyntheticsPanel'

const operationTypes: RemoteOperationType[] = ['telemetry.collect', 'inventory.refresh', 'agent.health_check']

function localDateInput(date: Date): string {
  const offset = date.getTimezoneOffset() * 60000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}

export function OperatorConsole() {
  const [token, setToken] = useState(() => sessionStorage.getItem('devicemesh.operatorToken') ?? '')
  const [devices, setDevices] = useState<Device[]>([])
  const [maintenance, setMaintenance] = useState<MaintenanceWindow[]>([])
  const [operations, setOperations] = useState<RemoteOperation[]>([])
  const [monitors, setMonitors] = useState<SyntheticMonitor[]>([])
  const [syntheticHealth, setSyntheticHealth] = useState<Record<string, SyntheticHealth>>({})
  const [error, setError] = useState<string | null>(null)
  const [deviceId, setDeviceId] = useState('')
  const [operationType, setOperationType] = useState<RemoteOperationType>('agent.health_check')
  const [maintenanceReason, setMaintenanceReason] = useState('Planned maintenance')
  const [maintenanceStart, setMaintenanceStart] = useState(() => localDateInput(new Date()))
  const [maintenanceEnd, setMaintenanceEnd] = useState(() => localDateInput(new Date(Date.now() + 60 * 60 * 1000)))
  const [monitorName, setMonitorName] = useState('')
  const [monitorKind, setMonitorKind] = useState<SyntheticMonitorKind>('http')
  const [monitorTarget, setMonitorTarget] = useState('https://example.com/health')
  const [monitorPort, setMonitorPort] = useState('443')

  const selectedDevice = useMemo(() => devices.find((device) => device.id === deviceId), [devices, deviceId])

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
      await queueRemoteOperation(token, deviceId, operationType)
      await refreshOperator()
      setError(null)
    } catch (reason) {
      setError(String(reason))
    }
  }

  const submitMonitor = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await createSyntheticMonitor(token, {
        name: monitorName || `${monitorKind.toUpperCase()} ${monitorTarget}`,
        kind: monitorKind,
        target: monitorTarget,
        port: monitorKind === 'tcp' ? Number(monitorPort) : null,
        deviceId: deviceId || null,
        intervalSeconds: 60,
        timeoutSeconds: 5,
        httpMethod: monitorKind === 'http' ? 'GET' : null,
        expectedStatus: monitorKind === 'http' ? 200 : null,
      })
      await refreshPublic()
      setError(null)
    } catch (reason) {
      setError(String(reason))
    }
  }

  return <main className="shell operatorConsole">
    <section className="hero">
      <div><div className="eyebrow">V1.3 operations & observability</div><h1>Operator Console</h1><p>Controlled maintenance, allowlisted remote operations, synthetic service monitoring and distributed probe consensus.</p></div>
      <a className="status" href="#/">Back to dashboard</a>
    </section>
    {error && <section className="errorBanner">{error}</section>}
    <section className="card panel operatorAuth">
      <div className="panelHeader"><div><div className="eyebrow">Authorization</div><h2>Operator session</h2></div></div>
      <div className="operatorRow">
        <input type="password" value={token} onChange={(event) => setToken(event.target.value)} placeholder="Operator bearer token" />
        <button onClick={() => void saveToken()}>Use token</button>
        <button onClick={() => void refresh()}>Refresh</button>
      </div>
      <p className="muted">The token is kept only in this browser tab via sessionStorage.</p>
    </section>
    <section className="contentGrid">
      <form className="card panel" onSubmit={submitMaintenance}>
        <div className="eyebrow">Noise control</div><h2>Maintenance window</h2>
        <label>Device<select value={deviceId} onChange={(event) => setDeviceId(event.target.value)}><option value="">Global</option>{devices.map((device) => <option key={device.id} value={device.id}>{device.hostname ?? device.id}</option>)}</select></label>
        <label>Starts<input type="datetime-local" value={maintenanceStart} onChange={(event) => setMaintenanceStart(event.target.value)} /></label>
        <label>Ends<input type="datetime-local" value={maintenanceEnd} onChange={(event) => setMaintenanceEnd(event.target.value)} /></label>
        <label>Reason<input value={maintenanceReason} onChange={(event) => setMaintenanceReason(event.target.value)} /></label>
        <button type="submit" disabled={!token}>Schedule maintenance</button>
        <div className="compactList">{maintenance.slice(0, 8).map((window) => <div key={window.id} className="compactItem"><div><strong>{window.deviceId ?? 'Global'}</strong><span>{window.reason}</span></div><div>{window.active ? 'Active' : 'Scheduled/ended'} {window.cancelledAt ? '· Cancelled' : ''}</div>{!window.cancelledAt && <button type="button" disabled={!token} onClick={() => void cancelMaintenanceWindow(token, window.id).then(refreshPublic).catch((reason: unknown) => setError(String(reason)))}>Cancel</button>}</div>)}</div>
      </form>
      <section className="card panel">
        <div className="eyebrow">Safe control plane</div><h2>Remote operation</h2>
        <p className="muted">No shell input exists. Only the V1.1 declarative allowlist is available.</p>
        <label>Device<select value={deviceId} onChange={(event) => setDeviceId(event.target.value)}>{devices.map((device) => <option key={device.id} value={device.id}>{device.hostname ?? device.id}</option>)}</select></label>
        <label>Operation<select value={operationType} onChange={(event) => setOperationType(event.target.value as RemoteOperationType)}>{operationTypes.map((type) => <option key={type} value={type}>{type}</option>)}</select></label>
        <button disabled={!token || !deviceId} onClick={() => void submitOperation()}>Queue operation</button>
        {selectedDevice && <p className="muted">Target: {selectedDevice.hostname ?? selectedDevice.id} · {selectedDevice.status}</p>}
        <div className="compactList">{operations.slice(0, 10).map((operation) => <div key={operation.id} className="compactItem"><div><strong>{operation.operationType}</strong><span>{operation.deviceId}</span></div><div>{operation.status}{operation.error ? ` · ${operation.error}` : ''}</div></div>)}</div>
      </section>
    </section>
    <form className="card panel" onSubmit={submitMonitor}>
      <div className="eyebrow">Service health</div><h2>Synthetic monitors</h2>
      <div className="operatorGrid">
        <label>Name<input value={monitorName} onChange={(event) => setMonitorName(event.target.value)} placeholder="Public API" /></label>
        <label>Kind<select value={monitorKind} onChange={(event) => setMonitorKind(event.target.value as SyntheticMonitorKind)}><option value="http">HTTP</option><option value="tcp">TCP</option><option value="icmp">ICMP</option></select></label>
        <label>Target<input value={monitorTarget} onChange={(event) => setMonitorTarget(event.target.value)} /></label>
        {monitorKind === 'tcp' && <label>Port<input type="number" min="1" max="65535" value={monitorPort} onChange={(event) => setMonitorPort(event.target.value)} /></label>}
      </div>
      <button type="submit" disabled={!token}>Create monitor</button>
      <div className="compactList syntheticList">{monitors.map((monitor) => {
        const health = syntheticHealth[monitor.id]
        const day = health?.windows.find((window) => window.label === '24h')
        return <div key={monitor.id} className="compactItem"><div><strong>{monitor.name}</strong><span>{monitor.kind.toUpperCase()} · {monitor.target}{monitor.port ? `:${monitor.port}` : ''}</span></div><div><strong>{day?.availabilityPercent == null ? 'No SLA yet' : `${day.availabilityPercent.toFixed(2)}% / 24h`}</strong><span>{day?.meanLatencyMs == null ? 'No latency yet' : `${day.meanLatencyMs.toFixed(0)} ms avg · ${day.p95LatencyMs?.toFixed(0) ?? '—'} ms p95`}</span></div><button type="button" disabled={!token} onClick={() => void setSyntheticMonitorEnabled(token, monitor.id, !monitor.enabled).then(refreshPublic).catch((reason: unknown) => setError(String(reason)))}>{monitor.enabled ? 'Disable' : 'Enable'}</button></div>
      })}</div>
    </form>
    <DistributedSyntheticsPanel token={token} monitors={monitors} />
  </main>
}
