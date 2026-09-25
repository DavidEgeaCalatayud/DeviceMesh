import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Device } from '../../entities/device/types'
import { listDevices } from '../../shared/api/client'
import { platformApi } from '../../shared/api/session'

type Service = {
  id: string
  name: string
  owner: string
  environment: string
  criticality: string
}

type Incident = {
  id: string
  title: string
  severity: string
  status: string
}

type SearchRow = {
  id: string
  kind: 'Device' | 'Service' | 'Incident'
  title: string
  detail: string
  href: string
  searchable: string
}

const normalize = (value: string) => value.trim().toLocaleLowerCase()

export function GlobalSearch() {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [devices, setDevices] = useState<Device[]>([])
  const [services, setServices] = useState<Service[]>([])
  const [incidents, setIncidents] = useState<Incident[]>([])
  const inputRef = useRef<HTMLInputElement>(null)
  const loaded = useRef(false)

  const loadResources = useCallback(() => {
    if (loaded.current) return
    loaded.current = true
    setLoading(true)
    setError('')
    Promise.all([
      listDevices(),
      platformApi<Service[]>('/service-catalog?limit=500'),
      platformApi<Incident[]>('/incidents?activeOnly=false&limit=500&offset=0'),
    ])
      .then(([deviceRows, serviceRows, incidentRows]) => {
        setDevices(deviceRows)
        setServices(serviceRows)
        setIncidents(incidentRows)
      })
      .catch(reason => {
        loaded.current = false
        setError(reason instanceof Error ? reason.message : 'Search data could not be loaded')
      })
      .finally(() => setLoading(false))
  }, [])

  const openSearch = useCallback(() => {
    setOpen(true)
    loadResources()
    queueMicrotask(() => inputRef.current?.focus())
  }, [loadResources])

  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        openSearch()
      }
      if (event.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', shortcut)
    return () => window.removeEventListener('keydown', shortcut)
  }, [openSearch])

  const rows = useMemo<SearchRow[]>(() => {
    const deviceRows = devices.map(device => ({
      id: `device:${device.id}`,
      kind: 'Device' as const,
      title: device.hostname || device.id,
      detail: `${device.status} · ${device.operatingSystem || 'Unknown OS'} · ${device.ipAddresses.join(', ') || 'No IP'}`,
      href: `#/devices/${encodeURIComponent(device.id)}`,
      searchable: [device.id, device.hostname, device.operatingSystem, ...device.ipAddresses, ...device.macAddresses]
        .filter(Boolean).join(' ').toLocaleLowerCase(),
    }))
    const serviceRows = services.map(service => ({
      id: `service:${service.id}`,
      kind: 'Service' as const,
      title: service.name,
      detail: `${service.environment} · ${service.criticality} · ${service.owner || 'Unassigned owner'}`,
      href: '#/services',
      searchable: [service.id, service.name, service.owner, service.environment, service.criticality]
        .join(' ').toLocaleLowerCase(),
    }))
    const incidentRows = incidents.map(incident => ({
      id: `incident:${incident.id}`,
      kind: 'Incident' as const,
      title: incident.title,
      detail: `${incident.severity} · ${incident.status}`,
      href: `#/incidents/${encodeURIComponent(incident.id)}`,
      searchable: [incident.id, incident.title, incident.severity, incident.status]
        .join(' ').toLocaleLowerCase(),
    }))
    return [...deviceRows, ...serviceRows, ...incidentRows]
  }, [devices, services, incidents])

  const matches = useMemo(() => {
    const terms = normalize(query).split(/\s+/).filter(Boolean)
    if (!terms.length) return rows.slice(0, 12)
    return rows.filter(row => terms.every(term => row.searchable.includes(term))).slice(0, 30)
  }, [query, rows])

  function closeAndNavigate(href: string) {
    setOpen(false)
    setQuery('')
    window.location.hash = href.slice(1)
  }

  function retry() {
    loaded.current = false
    loadResources()
  }

  return <>
    <button className="global-search-trigger" type="button" onClick={openSearch}>
      Search <kbd>Ctrl K</kbd>
    </button>
    {open && <div className="global-search-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) setOpen(false) }}>
      <section className="global-search-dialog" role="dialog" aria-modal="true" aria-label="Search DeviceMesh">
        <div className="global-search-header">
          <input
            ref={inputRef}
            type="search"
            aria-label="Search devices, services and incidents"
            placeholder="Search devices, services, incidents…"
            value={query}
            onChange={event => setQuery(event.target.value)}
          />
          <button type="button" onClick={() => setOpen(false)} aria-label="Close search">Close</button>
        </div>
        {loading && <p role="status">Loading searchable resources…</p>}
        {error && <p role="alert">{error} <button type="button" onClick={retry}>Retry</button></p>}
        {!loading && !error && matches.length === 0 && <p>No resources match “{query}”.</p>}
        {!loading && !error && matches.length > 0 && <ul className="global-search-results">
          {matches.map(row => <li key={row.id}>
            <button type="button" onClick={() => closeAndNavigate(row.href)}>
              <span className="global-search-kind">{row.kind}</span>
              <strong>{row.title}</strong>
              <span>{row.detail}</span>
            </button>
          </li>)}
        </ul>}
      </section>
    </div>}
  </>
}
