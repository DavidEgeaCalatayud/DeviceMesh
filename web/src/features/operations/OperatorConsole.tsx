import { type FormEvent, useCallback, useEffect, useState } from 'react'
import type { MaintenanceWindow } from '../../entities/health/types'
import type { RemoteOperation, RemoteOperationType } from '../../entities/operation/types'
import type { SyntheticMonitor, SyntheticMonitorCreate } from '../../entities/synthetic/types'
import {
  cancelMaintenanceWindow,
  createMaintenanceWindow,
  createSyntheticMonitor,
  disableSyntheticMonitor,
  listMaintenanceWindows,
  listRemoteOperations,
  listSyntheticMonitors,
  queueRemoteOperation,
} from '../../shared/api/client'

const TOKEN_KEY = 'devicemesh.operatorToken'
const operationTypes: { type: RemoteOperationType; label: string; hint: string }[] = [
  { type: 'agent.health_check', label: 'Agent health check', hint: 'Ask the enrolled agent for a structured health response.' },
  { type: 'telemetry.collect', label: 'Collect telemetry', hint: 'Request an immediate telemetry sample.' },
  { type: 'inventory.refresh', label: 'Refresh inventory', hint: 'Refresh host identity/inventory through the agent.' },
]

function loadToken(): string {
  try {
    return sessionStorage.getItem(TOKEN_KEY) ?? ''
  } catch {
    return ''
  }
}

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleString() : '—'
}

function statusClass(status: RemoteOperation['status']): string {
  if (status === 'succeeded') return 'up'
  if (status === 'failed' || status === 'expired') return 'down'
  return 'unknown'
}

export function OperatorConsole({
  deviceId,
  onChanged,
}: {
  deviceId: string
  onChanged?: () => void
}) {
  const [token, setToken] = useState(loadToken)
  const [tokenDraft, setTokenDraft] = useState(loadToken)
  const [maintenance, setMaintenance] = useState<MaintenanceWindow[]>([])
  const [operations, setOperations] = useState<RemoteOperation[]>([])
  const [monitors, setMonitors] = useState<SyntheticMonitor[]>([])
  const [reason, setReason] = useState('Planned maintenance')
  const [durationMinutes, setDurationMinutes] = useState(60)
  const [monitorName, setMonitorName] = useState('')
  const [monitorType, setMonitorType] = useState<'http' | 'tcp' | 'icmp'>('http')
  const [target, setTarget] = useState('')
  const [port, setPort] = useState('443')
  const [intervalSeconds, setIntervalSeconds] = useState(60)
  const [timeoutSeconds, setTimeoutSeconds] = useState(5)
  const [statusMin, setStatusMin] = useState(200)
  const [statusMax, setStatusMax] = useState(399)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refreshPublic = useCallback(async () => {
    const [nextMaintenance, nextMonitors] = await Promise.all([
      listMaintenanceWindows(undefined, deviceId, false),
      listSyntheticMonitors(undefined, deviceId),
    ])
    setMaintenance(nextMaintenance)
    setMonitors(nextMonitors)
  }, [deviceId])

  const refreshProtected = useCallback(async (operatorToken: string) => {
    if (!operatorToken) {
      setOperations([])
      return
    }
    setOperations(await listRemoteOperations(operatorToken, deviceId))
  }, [deviceId])

  useEffect(() => {
    void refreshPublic().catch((reason: unknown) => setError(String(reason)))
    if (token) void refreshProtected(token).catch(() => setToken(''))
  }, [refreshProtected, refreshPublic, token])

  function unlock(event: FormEvent) {
    event.preventDefault()
    const nextToken = tokenDraft.trim()
    if (!nextToken) return
    try {
      sessionStorage.setItem(TOKEN_KEY, nextToken)
    } catch {
      // Session-only persistence is optional; the in-memory token still works.
    }
    setToken(nextToken)
    setError(null)
  }

  function lock() {
    try {
      sessionStorage.removeItem(TOKEN_KEY)
    } catch {
      // Ignore unavailable browser storage.
    }
    setToken('')
    setTokenDraft('')
    setOperations([])
  }

  async function withMutation(key: string, action: () => Promise<unknown>) {
    if (!token) {
      setError('Unlock operator controls first.')
      return
    }
    setBusy(key)
    setError(null)
    try {
      await action()
      await Promise.all([refreshPublic(), refreshProtected(token)])
      onChanged?.()
    } catch (reason) {
      setError(String(reason))
    } finally {
      setBusy(null)
    }
  }

  function scheduleMaintenance(event: FormEvent) {
    event.preventDefault()
    const startsAt = new Date()
    const endsAt = new Date(startsAt.getTime() + durationMinutes * 60_000)
    void withMutation('maintenance-create', () => createMaintenanceWindow(token, {
      deviceId,
      startsAt: startsAt.toISOString(),
      endsAt: endsAt.toISOString(),
      reason: reason.trim(),
    }))
  }

  function runOperation(operationType: RemoteOperationType) {
    void withMutation(`operation-${operationType}`, () => queueRemoteOperation(token, deviceId, operationType))
  }

  function addMonitor(event: FormEvent) {
    event.preventDefault()
    const request: SyntheticMonitorCreate = {
      deviceId,
      name: monitorName.trim(),
      monitorType,
      target: target.trim(),
      intervalSeconds,
      timeoutSeconds,
    }
    if (monitorType === 'tcp') request.port = Number(port)
    if (monitorType === 'http') {
      request.expectedStatusMin = statusMin
      request.expectedStatusMax = statusMax
    }
    void withMutation('monitor-create', async () => {
      await createSyntheticMonitor(token, request)
      setMonitorName('')
      setTarget('')
    })
  }

  const activeMaintenance = maintenance.filter((window) => window.active)
  const enabledMonitors = monitors.filter((monitor) => monitor.enabled)

  return <section className="card operatorConsole">
    <div className="panelHeader operatorHeader">
      <div>
        <div className="eyebrow">Operator console</div>
        <h2>Controlled operations</h2>
        <p className="muted">Maintenance, allowlisted agent actions and synthetic monitor configuration.</p>
      </div>
      {token ? <button className="secondaryButton" type="button" onClick={lock}>Lock</button> : <span className="lockedBadge">locked</span>}
    </div>

    {!token && <form className="operatorUnlock" onSubmit={unlock}>
      <label>Operator token<input aria-label="Operator token" type="password" value={tokenDraft} onChange={(event) => setTokenDraft(event.target.value)} autoComplete="off" /></label>
      <button type="submit">Unlock controls</button>
      <p className="deviceMeta">Stored only in this browser session; it is never bundled into the frontend build.</p>
    </form>}

    {error && <div className="errorBanner">{error}</div>}

    <div className="operatorGrid">
      <article className="operatorSection">
        <div className="alertSectionTitle">Maintenance <span>{activeMaintenance.length} active</span></div>
        <form className="operatorForm" onSubmit={scheduleMaintenance}>
          <label>Reason<input value={reason} maxLength={512} required onChange={(event) => setReason(event.target.value)} /></label>
          <label>Duration<select value={durationMinutes} onChange={(event) => setDurationMinutes(Number(event.target.value))}>
            <option value={30}>30 minutes</option>
            <option value={60}>1 hour</option>
            <option value={120}>2 hours</option>
            <option value={240}>4 hours</option>
            <option value={480}>8 hours</option>
          </select></label>
          <button disabled={!token || busy === 'maintenance-create'} type="submit">Schedule now</button>
        </form>
        <div className="operatorHistory">
          {activeMaintenance.length === 0 ? <p className="muted">No active maintenance window.</p> : activeMaintenance.map((window) => <div className="operatorHistoryRow" key={window.id}>
            <div><strong>{window.reason}</strong><div className="deviceMeta">Until {formatDate(window.endsAt)} · #{window.id}</div></div>
            <button className="secondaryButton" disabled={!token || busy === `maintenance-${window.id}`} type="button" onClick={() => void withMutation(`maintenance-${window.id}`, () => cancelMaintenanceWindow(token, window.id))}>Cancel</button>
          </div>)}
        </div>
      </article>

      <article className="operatorSection">
        <div className="alertSectionTitle">Remote operations <span>allowlist only</span></div>
        <div className="operationActions">
          {operationTypes.map((operation) => <button disabled={!token || busy === `operation-${operation.type}`} type="button" key={operation.type} onClick={() => runOperation(operation.type)}>
            <strong>{operation.label}</strong><span>{operation.hint}</span>
          </button>)}
        </div>
        <div className="operatorHistory">
          {token && operations.length === 0 && <p className="muted">No remote operations recorded for this device.</p>}
          {operations.slice(0, 10).map((operation) => <div className="operationHistoryRow" key={operation.id}>
            <div className="operationHistoryHeader"><strong>{operation.operationType}</strong><span className={`healthState ${statusClass(operation.status)}`}>{operation.status}</span></div>
            <div className="deviceMeta">Queued {formatDate(operation.createdAt)} · completed {formatDate(operation.completedAt)}</div>
            {operation.error && <code className="operationError">{operation.error}</code>}
            {Object.keys(operation.result).length > 0 && <pre>{JSON.stringify(operation.result, null, 2)}</pre>}
          </div>)}
        </div>
      </article>
    </div>

    <article className="operatorSection syntheticOperatorSection">
      <div className="alertSectionTitle">Synthetic monitors <span>{enabledMonitors.length} enabled</span></div>
      <form className="syntheticMonitorForm" onSubmit={addMonitor}>
        <label>Name<input required maxLength={128} placeholder="Public API" value={monitorName} onChange={(event) => setMonitorName(event.target.value)} /></label>
        <label>Protocol<select value={monitorType} onChange={(event) => setMonitorType(event.target.value as 'http' | 'tcp' | 'icmp')}>
          <option value="http">HTTP(S)</option>
          <option value="tcp">TCP</option>
          <option value="icmp">ICMP</option>
        </select></label>
        <label className="targetField">Target<input required maxLength={2048} placeholder={monitorType === 'http' ? 'https://example.com/health' : 'example.com'} value={target} onChange={(event) => setTarget(event.target.value)} /></label>
        {monitorType === 'tcp' && <label>Port<input type="number" min={1} max={65535} value={port} onChange={(event) => setPort(event.target.value)} /></label>}
        {monitorType === 'http' && <>
          <label>HTTP min<input type="number" min={100} max={599} value={statusMin} onChange={(event) => setStatusMin(Number(event.target.value))} /></label>
          <label>HTTP max<input type="number" min={100} max={599} value={statusMax} onChange={(event) => setStatusMax(Number(event.target.value))} /></label>
        </>}
        <label>Interval<input type="number" min={15} max={3600} value={intervalSeconds} onChange={(event) => setIntervalSeconds(Number(event.target.value))} /></label>
        <label>Timeout<input type="number" min={1} max={30} value={timeoutSeconds} onChange={(event) => setTimeoutSeconds(Number(event.target.value))} /></label>
        <button disabled={!token || busy === 'monitor-create'} type="submit">Add monitor</button>
      </form>
      <div className="monitorDefinitionList">
        {monitors.length === 0 ? <p className="muted">No monitor definitions for this device.</p> : monitors.map((monitor) => <div className="operatorHistoryRow" key={monitor.id}>
          <div><strong>{monitor.name}</strong><div className="deviceMeta">{monitor.monitorType.toUpperCase()} · {monitor.target}{monitor.port ? `:${monitor.port}` : ''} · every {monitor.intervalSeconds}s · {monitor.enabled ? 'enabled' : 'disabled'}</div></div>
          {monitor.enabled && <button className="secondaryButton" disabled={!token || busy === `monitor-${monitor.id}`} type="button" onClick={() => void withMutation(`monitor-${monitor.id}`, () => disableSyntheticMonitor(token, monitor.id))}>Disable</button>}
        </div>)}
      </div>
    </article>
  </section>
}
