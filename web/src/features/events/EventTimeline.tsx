import type { DeviceEvent } from '../../entities/event/types'

function eventTitle(event: DeviceEvent): string {
  const hostname = typeof event.attributes.hostname === 'string' ? event.attributes.hostname : event.deviceId
  switch (event.name) {
    case 'DEVICE_DISCOVERED': return `${hostname} discovered`
    case 'AGENT_CONNECTED': return `${hostname} agent connected`
    case 'DEVICE_ONLINE': return `${hostname} online`
    case 'IP_CHANGED': return `${hostname} changed network address`
    default: return event.name.replaceAll('_', ' ').toLowerCase()
  }
}

export function EventTimeline({ events }: { events: DeviceEvent[] }) {
  if (events.length === 0) return <p className="muted">No network events recorded yet.</p>
  return <div className="timeline">{events.map((event, index) => <div className="timelineItem" key={`${event.deviceId}-${event.timestamp}-${index}`}>
    <span className={`eventDot ${event.severity}`} />
    <div className="timelineBody"><strong>{eventTitle(event)}</strong><div className="muted">{new Date(event.timestamp).toLocaleString()}</div></div>
  </div>)}</div>
}
