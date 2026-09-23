import { useMemo, useState } from 'react'
import type { DeviceEvent } from '../../entities/event/types'

type TimelineFilter = 'all' | 'devices' | 'alerts' | 'warning'

function eventTitle(event: DeviceEvent): string {
  const hostname = typeof event.attributes.hostname === 'string' ? event.attributes.hostname : event.deviceId
  switch (event.name) {
    case 'DEVICE_DISCOVERED': return `${hostname} discovered`
    case 'AGENT_CONNECTED': return `${hostname} agent connected`
    case 'DEVICE_ONLINE': return `${hostname} online`
    case 'DEVICE_OFFLINE': return `${hostname} offline`
    case 'IP_CHANGED': return `${hostname} changed network address`
    case 'ALERT_OPENED': return `${hostname} alert opened`
    case 'ALERT_RECOVERED': return `${hostname} alert recovered`
    default: return event.name.replaceAll('_', ' ').toLowerCase()
  }
}

function matchesFilter(event: DeviceEvent, filter: TimelineFilter): boolean {
  if (filter === 'alerts') return event.name.startsWith('ALERT_')
  if (filter === 'devices') return !event.name.startsWith('ALERT_')
  if (filter === 'warning') return event.severity === 'warning' || event.severity === 'critical'
  return true
}

function searchableText(event: DeviceEvent): string {
  return [
    event.deviceId,
    event.name,
    eventTitle(event),
    ...Object.values(event.attributes).filter((value): value is string => typeof value === 'string'),
  ].join(' ').toLowerCase()
}

export function EventTimeline({ events }: { events: DeviceEvent[] }) {
  const [filter, setFilter] = useState<TimelineFilter>('all')
  const [query, setQuery] = useState('')
  const visibleEvents = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    return events.filter((event) => {
      if (!matchesFilter(event, filter)) return false
      return normalizedQuery.length === 0 || searchableText(event).includes(normalizedQuery)
    })
  }, [events, filter, query])

  if (events.length === 0) return <p className="muted">No network events recorded yet.</p>

  return <>
    <div className="timelineControls" aria-label="Timeline filters">
      <div className="timelineFilterButtons">
        {([
          ['all', 'All'],
          ['devices', 'Devices'],
          ['alerts', 'Alerts'],
          ['warning', 'Warning+'],
        ] as const).map(([value, label]) => <button
          className={filter === value ? 'filterButton active' : 'filterButton'}
          key={value}
          onClick={() => setFilter(value)}
          type="button"
        >{label}</button>)}
      </div>
      <input
        aria-label="Search timeline"
        className="timelineSearch"
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search device or event…"
        type="search"
        value={query}
      />
    </div>
    {visibleEvents.length === 0
      ? <p className="muted">No events match the current filters.</p>
      : <div className="timeline">{visibleEvents.map((event, index) => <div className="timelineItem" key={`${event.deviceId}-${event.timestamp}-${index}`}>
        <span className={`eventDot ${event.severity}`} />
        <div className="timelineBody"><strong>{eventTitle(event)}</strong><div className="muted">{new Date(event.timestamp).toLocaleString()}</div></div>
      </div>)}</div>}
  </>
}
