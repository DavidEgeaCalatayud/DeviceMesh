import type { AlertIncident } from '../../entities/alert/types'
import type { Device } from '../../entities/device/types'

function deviceLabel(deviceId: string, devices: Device[]): string {
  const device = devices.find((item) => item.id === deviceId)
  return device?.hostname ?? deviceId
}

function thresholdLabel(alert: AlertIncident): string {
  const duration = alert.durationSeconds > 0 ? ` for ${alert.durationSeconds}s` : ''
  return `${alert.metricName} ${alert.operator} ${alert.threshold}${duration}`
}

function formatTime(value: string): string {
  return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export function AlertPanel({ alerts, devices }: { alerts: AlertIncident[]; devices: Device[] }) {
  const active = alerts.filter((alert) => alert.active)
  const recovered = alerts.filter((alert) => !alert.active).slice(0, 5)

  return <div className="alertPanelBody">
    <section>
      <div className="alertSectionTitle">Active incidents <span>{active.length}</span></div>
      {active.length === 0
        ? <p className="muted">No active threshold alerts.</p>
        : <div className="alertList">{active.map((alert) => <div className={`alertItem activeAlert ${alert.silenced ? 'silencedAlert' : ''}`} key={alert.id}>
          <div>
            <div className="alertIdentity"><strong>{deviceLabel(alert.deviceId, devices)}</strong>{alert.silenced && <span className="maintenanceBadge">silenced</span>}</div>
            <div className="muted">{thresholdLabel(alert)}</div>
            {alert.silenced && <div className="deviceMeta">Maintenance window #{alert.maintenanceWindowId} · incident retained, notification noise suppressed</div>}
          </div>
          <div className="alertTime">since {formatTime(alert.openedAt)}</div>
        </div>)}</div>}
    </section>
    <section>
      <div className="alertSectionTitle">Recent recoveries <span>{recovered.length}</span></div>
      {recovered.length === 0
        ? <p className="muted">No recovered incidents yet.</p>
        : <div className="alertList">{recovered.map((alert) => <div className="alertItem" key={alert.id}>
          <div>
            <strong>{deviceLabel(alert.deviceId, devices)}</strong>
            <div className="muted">{thresholdLabel(alert)}</div>
          </div>
          <div className="alertTime">recovered {alert.closedAt ? formatTime(alert.closedAt) : '—'}</div>
        </div>)}</div>}
    </section>
  </div>
}
