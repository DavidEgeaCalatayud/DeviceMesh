import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { apiBase, apiFetch, platformApi } from '../../shared/api/session'

type Audit = {
  id: string
  timestamp: string
  actor: string
  action: string
  resource: string
  sourceIp: string | null
  requestId: string | null
  metadata: Record<string, unknown>
}

type Filters = {
  search: string
  actor: string
  action: string
  resource: string
  sourceIp: string
  requestId: string
  since: string
  until: string
}

const emptyFilters: Filters = {
  search: '', actor: '', action: '', resource: '', sourceIp: '', requestId: '', since: '', until: '',
}

const pageSize = 100
const formatDate = (value: string) => new Date(value).toLocaleString()
const errorText = (value: unknown) => value instanceof Error ? value.message : 'Request failed'

function appendFilters(query: URLSearchParams, filters: Filters) {
  for (const [key, value] of Object.entries(filters)) {
    if (!value) continue
    if (key === 'since' || key === 'until') query.set(key, new Date(value).toISOString())
    else query.set(key, value)
  }
  return query
}

function queryString(filters: Filters, offset = 0) {
  return appendFilters(new URLSearchParams({ limit: String(pageSize), offset: String(offset) }), filters).toString()
}

function exportQueryString(filters: Filters) {
  return appendFilters(new URLSearchParams(), filters).toString()
}

export function AuditPage() {
  const [filters, setFilters] = useState<Filters>(emptyFilters)
  const [applied, setApplied] = useState<Filters>(emptyFilters)
  const [events, setEvents] = useState<Audit[]>([])
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState('')
  const query = useMemo(() => queryString(applied, offset), [applied, offset])

  useEffect(() => {
    let active = true
    platformApi<Audit[]>(`/admin/audit-log?${query}`)
      .then(data => { if (active) { setEvents(data); setError('') } })
      .catch(reason => { if (active) setError(errorText(reason)) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [query])

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLoading(true)
    setOffset(0)
    setApplied(filters)
  }

  function clearFilters() {
    setLoading(true)
    setFilters(emptyFilters)
    setApplied(emptyFilters)
    setOffset(0)
  }

  function previousPage() {
    setLoading(true)
    setOffset(value => Math.max(0, value - pageSize))
  }

  function nextPage() {
    setLoading(true)
    setOffset(value => value + pageSize)
  }

  async function exportCsv() {
    setExporting(true); setError('')
    try {
      const exportQuery = exportQueryString(applied)
      const response = await apiFetch(`${apiBase}/api/v1/admin/audit-log.csv${exportQuery ? `?${exportQuery}` : ''}`)
      if (!response.ok) throw new Error(`Export failed (${response.status})`)
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = 'devicemesh-audit-log.csv'
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (reason) { setError(errorText(reason)) } finally { setExporting(false) }
  }

  return <main className="platform-page">
    <h1>Audit log</h1>
    <p>Immutable security and operator activity recorded by the DeviceMesh control plane.</p>
    {error && <p role="alert">{error}</p>}
    <form className="platform-form" onSubmit={submit}>
      <label>Search<input type="search" value={filters.search} maxLength={256} onChange={e => setFilters(v => ({ ...v, search: e.target.value }))} placeholder="actor, action or resource" /></label>
      <label>Actor<input value={filters.actor} maxLength={128} onChange={e => setFilters(v => ({ ...v, actor: e.target.value }))} /></label>
      <label>Action<input value={filters.action} maxLength={128} onChange={e => setFilters(v => ({ ...v, action: e.target.value }))} placeholder="incident.updated" /></label>
      <label>Resource<input value={filters.resource} maxLength={256} onChange={e => setFilters(v => ({ ...v, resource: e.target.value }))} /></label>
      <label>Source IP<input value={filters.sourceIp} maxLength={64} onChange={e => setFilters(v => ({ ...v, sourceIp: e.target.value }))} /></label>
      <label>Request ID<input value={filters.requestId} maxLength={64} onChange={e => setFilters(v => ({ ...v, requestId: e.target.value }))} /></label>
      <label>From<input type="datetime-local" value={filters.since} onChange={e => setFilters(v => ({ ...v, since: e.target.value }))} /></label>
      <label>To<input type="datetime-local" value={filters.until} onChange={e => setFilters(v => ({ ...v, until: e.target.value }))} /></label>
      <div className="platform-actions"><button type="submit">Apply filters</button><button type="button" onClick={clearFilters}>Clear</button><button type="button" disabled={exporting} onClick={() => void exportCsv()}>{exporting ? 'Exporting…' : 'Export CSV'}</button></div>
    </form>
    {loading && <p role="status">Loading audit events…</p>}
    {!loading && events.length === 0 && <p>No audit events match this view.</p>}
    <div className="table-scroll"><table><thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Resource</th><th>Source</th><th>Request</th><th>Metadata</th></tr></thead><tbody>{events.map(event => <tr key={event.id}>
      <td>{formatDate(event.timestamp)}</td><td>{event.actor}</td><td>{event.action}</td><td>{event.resource}</td><td>{event.sourceIp ?? '—'}</td><td><code>{event.requestId ?? '—'}</code></td><td><details><summary>Details</summary><pre>{JSON.stringify(event.metadata, null, 2)}</pre></details></td>
    </tr>)}</tbody></table></div>
    <div className="platform-actions"><button disabled={offset === 0 || loading} onClick={previousPage}>Previous</button><span>{offset + 1}–{offset + events.length}</span><button disabled={events.length < pageSize || loading} onClick={nextPage}>Next</button></div>
  </main>
}
