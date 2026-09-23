import type { DeviceHealth, Outage, SlaWindow } from '../../entities/health/types'

function formatDuration(seconds: number | null): string {
  if (seconds === null) return '—'
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

function availability(window: SlaWindow): string {
  return window.availabilityPercent === null ? 'No data' : `${window.availabilityPercent.toFixed(3)}%`
}

function SlaCard({ window }: { window: SlaWindow }) {
  return <article className="slaCard">
    <div className="slaCardHeader"><span>{window.label}</span><strong>{availability(window)}</strong></div>
    <div className="slaMeta"><span>Downtime <b>{formatDuration(window.downtimeSeconds)}</b></span><span>Outages <b>{window.outageCount}</b></span></div>
    <div className="slaMeta"><span>Longest <b>{formatDuration(window.longestOutageSeconds)}</b></span><span>Mean recovery <b>{formatDuration(window.meanRecoverySeconds)}</b></span></div>
    <div className="deviceMeta">Observed {formatDuration(window.monitoredSeconds)} in this window</div>
  </article>
}

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString()
}

export function DeviceHealthPanel({ health, outages }: { health: DeviceHealth; outages: Outage[] }) {
  return <section className="card healthPanel">
    <div className="panelHeader healthHeader">
      <div><div className="eyebrow">Service-level health</div><h2>Availability & outages</h2></div>
      <div className="healthStateGroup">
        {health.maintenanceActive && <span className="maintenanceBadge">maintenance</span>}
        <span className={`healthState ${health.currentState ?? 'unknown'}`}>{health.currentState ?? 'unknown'}</span>
      </div>
    </div>

    {health.currentState === 'offline' && <div className="outageBanner">
      <strong>Current outage</strong>
      <span>{formatDuration(health.currentOutageSeconds)} without an online transition.</span>
    </div>}
    {health.maintenanceActive && <div className="maintenanceBanner">
      Alert notification semantics are silenced by maintenance window #{health.maintenanceWindowId}; telemetry and incidents continue to be recorded.
    </div>}

    <div className="slaGrid">
      {health.windows.map((window) => <SlaCard window={window} key={window.label} />)}
    </div>

    <div className="outageHistory">
      <div className="alertSectionTitle">Recent outages <span>{outages.length}</span></div>
      {outages.length === 0
        ? <p className="muted">No outage interval has been recorded in the selected 30-day history.</p>
        : <div className="outageList">{outages.slice(0, 10).map((outage) => <div className="outageRow" key={outage.id}>
          <div><strong>{outage.active ? 'Active outage' : 'Recovered outage'}</strong><div className="deviceMeta">Started {formatTimestamp(outage.startedAt)} · {outage.source}</div></div>
          <div className="outageDuration">{formatDuration(outage.durationSeconds)}</div>
        </div>)}</div>}
    </div>
  </section>
}
