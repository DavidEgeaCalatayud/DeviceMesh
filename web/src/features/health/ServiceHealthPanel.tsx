import type { SyntheticHealth, SyntheticSlaWindow } from '../../entities/synthetic/types'

function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  const days = Math.floor(total / 86400)
  const hours = Math.floor((total % 86400) / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const secs = total % 60
  if (days > 0) return `${days}d ${hours}h`
  if (hours > 0) return `${hours}h ${minutes}m`
  if (minutes > 0) return `${minutes}m ${secs}s`
  return `${secs}s`
}

function availability(window: SyntheticSlaWindow): string {
  return window.availabilityPercent === null ? 'No data' : `${window.availabilityPercent.toFixed(3)}%`
}

function latency(value: number | null): string {
  return value === null ? '—' : `${value.toFixed(1)} ms`
}

function targetLabel(health: SyntheticHealth): string {
  if (health.monitor.monitorType === 'tcp' && health.monitor.port) {
    return `${health.monitor.target}:${health.monitor.port}`
  }
  return health.monitor.target
}

export function ServiceHealthPanel({ services }: { services: SyntheticHealth[] }) {
  return <section className="card healthPanel serviceHealthPanel">
    <div className="panelHeader healthHeader">
      <div>
        <div className="eyebrow">Service health</div>
        <h2>External synthetic availability</h2>
        <p className="muted">Observed from the DeviceMesh probe, independently of agent heartbeats.</p>
      </div>
      <span className="serviceCountBadge">{services.length} monitor{services.length === 1 ? '' : 's'}</span>
    </div>

    {services.length === 0 ? <div className="emptyState">
      <strong>No synthetic monitors configured</strong>
      <p className="muted">Add an HTTP, TCP or ICMP check from the operator console below.</p>
    </div> : <div className="serviceHealthList">
      {services.map((health) => <article className="syntheticMonitorCard" key={health.monitor.id}>
        <div className="syntheticMonitorHeader">
          <div>
            <div className="syntheticMonitorTitle">
              <strong>{health.monitor.name}</strong>
              <span className="monitorTypeBadge">{health.monitor.monitorType.toUpperCase()}</span>
              {health.stale && <span className="staleBadge">stale</span>}
            </div>
            <div className="deviceMeta">{targetLabel(health)}</div>
          </div>
          <span className={`healthState ${health.currentState}`}>{health.currentState}</span>
        </div>

        <div className="syntheticLatest">
          <span>Latency <b>{latency(health.latestLatencyMs)}</b></span>
          {health.latestHttpStatus !== null && <span>HTTP <b>{health.latestHttpStatus}</b></span>}
          <span>Last check <b>{health.lastObservedAt ? new Date(health.lastObservedAt).toLocaleString() : 'Never'}</b></span>
        </div>

        {health.currentState === 'down' && <div className="outageBanner">
          <strong>Service outage</strong>
          <span>{formatDuration(health.currentOutageSeconds)} since the first failed check in this outage.</span>
          {health.latestFailureReason && <code>{health.latestFailureReason}</code>}
        </div>}
        {health.stale && <div className="maintenanceBanner">
          Probe coverage expired. Unobserved time is excluded from availability instead of being assumed up or down.
        </div>}

        <div className="slaGrid">
          {health.windows.map((window) => <div className="slaCard" key={window.label}>
            <div className="slaCardHeader"><span>{window.label}</span><strong>{availability(window)}</strong></div>
            <div className="slaMeta"><span>Downtime <b>{formatDuration(window.downtimeSeconds)}</b></span><span>Outages <b>{window.outageCount}</b></span></div>
            <div className="slaMeta"><span>P50 <b>{latency(window.latencyP50Ms)}</b></span><span>P95 <b>{latency(window.latencyP95Ms)}</b></span></div>
            <div className="deviceMeta">Observed {formatDuration(window.monitoredSeconds)}</div>
          </div>)}
        </div>

        <div className="outageHistory compactOutages">
          <div className="alertSectionTitle">Recent service outages <span>{health.outages.length}</span></div>
          {health.outages.length === 0 ? <p className="muted">No synthetic outage recorded in the last 30 days.</p> : health.outages.slice(0, 5).map((outage) => <div className="outageRow" key={`${outage.startedAt}-${outage.endedAt ?? 'active'}`}>
            <div><strong>{outage.active ? 'Active outage' : 'Recovered outage'}</strong><div className="deviceMeta">Started {new Date(outage.startedAt).toLocaleString()}{outage.lastFailureReason ? ` · ${outage.lastFailureReason}` : ''}</div></div>
            <div className="outageDuration">{formatDuration(outage.durationSeconds)}</div>
          </div>)}
        </div>
      </article>)}
    </div>}
  </section>
}
