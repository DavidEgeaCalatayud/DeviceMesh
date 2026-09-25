import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { getToken, platformApi, signIn } from '../../shared/api/session'

type Service = { id: string; name: string; description: string; owner: string; environment: string; criticality: string; monitorIds: string[] }
type Monitor = { id: string; name: string }
type Slo = { id: string; name: string; status: string; actualPercent: number | null; targetPercent: number; remainingFailedChecks: number | null; totalChecks: number; burnRates: Record<string, number | null> }
type Timeline = { id: string; timestamp: string; actor: string; action: string; details: Record<string, unknown> }
type Incident = { id: string; title: string; severity: string; status: string; openedAt: string; assignedTo: string | null; rootCause: string; resolution: string; timeline?: Timeline[] }
type User = { id: string; username: string; role: string; enabled: boolean }
type Audit = { id: string; timestamp: string; actor: string; action: string; resource: string }
const date = (value: string) => new Date(value).toLocaleString()
const errorText = (value: unknown) => value instanceof Error ? value.message : 'Request failed'

export function LoginPage() {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    setBusy(true)
    try {
      await signIn(String(data.get('username')), String(data.get('password')))
      window.location.hash = '#/'
    } catch (reason) { setError(errorText(reason)) } finally { setBusy(false) }
  }
  return <main className="platform-page"><h1>Sign in to DeviceMesh</h1><p>Use your server account to view and manage your fleet.</p>
    <form onSubmit={(event) => void submit(event)} className="platform-form">
      <label>Username<input name="username" autoComplete="username" required maxLength={128} /></label>
      <label>Password<input name="password" type="password" autoComplete="current-password" required maxLength={256} /></label>
      <button disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
    </form>{error && <p role="alert">{error}</p>}
  </main>
}

export function ServicesPage() {
  const [services, setServices] = useState<Service[]>([])
  const [monitors, setMonitors] = useState<Monitor[]>([])
  const [selected, setSelected] = useState('')
  const [slos, setSlos] = useState<Slo[]>([])
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [role, setRole] = useState('viewer')
  const canEdit = role !== 'viewer'
  async function load() {
    const [catalog, definitions] = await Promise.all([platformApi<Service[]>('/service-catalog?limit=200'), platformApi<Monitor[]>('/synthetic-monitors')])
    setServices(catalog); setMonitors(definitions)
  }
  useEffect(() => {
    let active = true
    Promise.all([platformApi<Service[]>('/service-catalog?limit=200'), platformApi<Monitor[]>('/synthetic-monitors')])
      .then(([catalog, definitions]) => { if (active) { setServices(catalog); setMonitors(definitions) } })
      .catch((reason) => { if (active) setError(errorText(reason)) }).finally(() => { if (active) setLoading(false) })
    if (getToken()) void platformApi<{ role: string }>('/auth/me').then(user => { if (active) setRole(user.role) }).catch(() => {})
    return () => { active = false }
  }, [])
  useEffect(() => {
    if (!selected) return
    let active = true
    platformApi<Slo[]>(`/service-catalog/${selected}/slos`).then(data => { if (active) setSlos(data) })
      .catch(reason => { if (active) setError(errorText(reason)) })
    return () => { active = false }
  }, [selected])
  async function mutate(work: () => Promise<unknown>) {
    setBusy(true); setError('')
    try { await work(); await load(); if (selected) setSlos(await platformApi<Slo[]>(`/service-catalog/${selected}/slos`)) }
    catch (reason) { setError(errorText(reason)) } finally { setBusy(false) }
  }
  return <main className="platform-page"><h1>Services</h1><p>Group synthetic monitors around the services your team operates.</p>
    {error && <p role="alert">{error}</p>}{loading && <p role="status">Loading services…</p>}
    <label>Search services<input value={query} onChange={e => setQuery(e.target.value)} type="search" /></label>
    {!loading && services.length === 0 && <p>No services yet. Create one and associate its monitors.</p>}
    <div className="platform-grid">{services.filter(s => s.name.toLowerCase().includes(query.toLowerCase())).map(service => <button className="service-card" aria-pressed={selected === service.id} key={service.id} onClick={() => { setSelected(service.id); setSlos([]) }}>
      <strong>{service.name}</strong><span>{service.environment} · {service.criticality}</span><span>{service.owner || 'Unassigned owner'} · {service.monitorIds.length} monitors</span>
    </button>)}</div>
    {selected && <section><h2>{services.find(s => s.id === selected)?.name}: objectives</h2><p>SLI: successful checks / total checks. Missing observations are not assumed healthy.</p>
      {slos.length === 0 && <p>No SLOs configured.</p>}{slos.map(slo => <article className="platform-card" key={slo.id}><h3>{slo.name} · {slo.status}</h3><p>{slo.actualPercent?.toFixed(3) ?? 'Unknown'}% / target {slo.targetPercent}% · {slo.totalChecks} checks</p><p>Remaining budget: {slo.remainingFailedChecks?.toFixed(2) ?? 'Unknown'} failed checks. Burn rate 1h: {slo.burnRates['1h']?.toFixed(2) ?? 'Unknown'}×; 6h: {slo.burnRates['6h']?.toFixed(2) ?? 'Unknown'}×.</p></article>)}
      {canEdit && <><form className="platform-form" onSubmit={e => { e.preventDefault(); const data = new FormData(e.currentTarget); void mutate(() => platformApi(`/service-catalog/${selected}/monitors/${data.get('monitor')}`, { method: 'PUT' })) }}>
        <label>Associate monitor<select name="monitor" required>{monitors.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label><button disabled={busy || !monitors.length}>Associate</button>
      </form><form className="platform-form" onSubmit={e => { e.preventDefault(); const data = new FormData(e.currentTarget); void mutate(() => platformApi(`/service-catalog/${selected}/slos`, { method: 'POST', body: JSON.stringify({ name: data.get('name'), monitorId: data.get('monitor'), targetPercent: Number(data.get('target')), windowDays: Number(data.get('window')) }) })) }}>
        <label>Objective name<input name="name" required maxLength={255} /></label><label>Monitor<select name="monitor" required>{monitors.filter(m => services.find(s => s.id === selected)?.monitorIds.includes(m.id)).map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label>
        <label>Target %<input name="target" type="number" min="0.001" max="99.9999" step="0.0001" defaultValue="99.9" required /></label><label>Window<select name="window"><option value="7">7 days</option><option value="30">30 days</option><option value="90">90 days</option></select></label><button disabled={busy}>Create SLO</button>
      </form></>}
    </section>}
    {canEdit && <section><h2>Create service</h2><form className="platform-form" onSubmit={e => { e.preventDefault(); const data = new FormData(e.currentTarget); void mutate(() => platformApi('/service-catalog', { method: 'POST', body: JSON.stringify({ name: data.get('name'), owner: data.get('owner'), environment: data.get('environment') }) })) }}>
      <label>Name<input name="name" required maxLength={255} /></label><label>Owner<input name="owner" maxLength={128} /></label><label>Environment<input name="environment" required maxLength={64} defaultValue="production" /></label><button disabled={busy}>Create service</button>
    </form></section>}
  </main>
}

export function IncidentsPage({ incidentId }: { incidentId?: string }) {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [detail, setDetail] = useState<Incident | null>(null)
  const [error, setError] = useState('')
  const [activeOnly, setActiveOnly] = useState(true)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [role, setRole] = useState('viewer')
  useEffect(() => {
    let active = true
    const request = incidentId ? platformApi<Incident>(`/incidents/${encodeURIComponent(incidentId)}`).then(data => { if (active) setDetail(data) })
      : platformApi<Incident[]>(`/incidents?activeOnly=${activeOnly}&limit=50&offset=${offset}`).then(data => { if (active) setIncidents(data) })
    request.catch(reason => { if (active) setError(errorText(reason)) }).finally(() => { if (active) setLoading(false) })
    if (getToken()) void platformApi<{ role: string }>('/auth/me').then(user => { if (active) setRole(user.role) }).catch(() => {})
    return () => { active = false }
  }, [incidentId, activeOnly, offset])
  async function update(changes: Record<string, unknown>) {
    setBusy(true); setError('')
    try { await platformApi(`/incidents/${incidentId}`, { method: 'PATCH', body: JSON.stringify(changes) }); setDetail(await platformApi<Incident>(`/incidents/${incidentId}`)) }
    catch (reason) { setError(errorText(reason)) } finally { setBusy(false) }
  }
  return <main className="platform-page"><h1>{detail && incidentId ? detail.title : 'Incidents'}</h1>{error && <p role="alert">{error}</p>}{loading && <p role="status">Loading incidents…</p>}
    {!incidentId && <><label><input type="checkbox" checked={activeOnly} onChange={e => { setActiveOnly(e.target.checked); setOffset(0) }} />Open incidents only</label>
      {!loading && incidents.length === 0 && <p>No incidents in this view.</p>}
      <ul className="incident-list">{incidents.map(incident => <li key={incident.id}><a href={`#/incidents/${incident.id}`}><strong>{incident.severity} · {incident.title}</strong></a><span>{incident.status} · {date(incident.openedAt)}</span></li>)}</ul>
      <div className="platform-actions"><button disabled={offset === 0} onClick={() => setOffset(v => Math.max(0, v - 50))}>Previous</button><button disabled={incidents.length < 50} onClick={() => setOffset(v => v + 50)}>Next</button></div></>}
    {incidentId && detail && <><p>{detail.severity} · {detail.status} · assigned to {detail.assignedTo || 'nobody'}</p><a href="#/incidents">All incidents</a>
      {role !== 'viewer' && <><div className="platform-actions">
        {detail.status === 'open' && <button disabled={busy} onClick={() => void update({ status: 'acknowledged' })}>Acknowledge</button>}
        {['open', 'acknowledged', 'mitigated'].includes(detail.status) && <button disabled={busy} onClick={() => void update({ status: 'investigating' })}>Investigate</button>}
        {['acknowledged', 'investigating'].includes(detail.status) && <button disabled={busy} onClick={() => void update({ status: 'mitigated' })}>Mark mitigated</button>}
        {detail.status === 'resolved' && <button disabled={busy} onClick={() => void update({ status: 'open' })}>Reopen</button>}
      </div><form key={detail.id} className="platform-form" onSubmit={e => { e.preventDefault(); const data = new FormData(e.currentTarget); void update({ assignedTo: data.get('assignee'), severity: data.get('severity'), rootCause: data.get('cause'), resolution: data.get('resolution'), ...(data.get('resolve') ? { status: 'resolved' } : {}) }) }}>
        <label>Assignee<input name="assignee" defaultValue={detail.assignedTo ?? ''} maxLength={128} /></label><label>Severity<select name="severity" defaultValue={detail.severity}>{['SEV1', 'SEV2', 'SEV3', 'SEV4'].map(s => <option key={s}>{s}</option>)}</select></label>
        <label>Root cause<textarea name="cause" defaultValue={detail.rootCause} maxLength={10000} /></label><label>Resolution<textarea name="resolution" defaultValue={detail.resolution} maxLength={10000} /></label>
        {detail.status !== 'resolved' && <label><input type="checkbox" name="resolve" />Resolve with this explanation</label>}<button disabled={busy}>Save incident</button>
      </form><form className="platform-form" onSubmit={e => { e.preventDefault(); const form = e.currentTarget; const data = new FormData(form); void update({ note: data.get('note') }).then(() => form.reset()) }}><label>Timeline note<textarea name="note" required maxLength={10000} /></label><button disabled={busy}>Add note</button></form></>}
      <h2>Timeline</h2><ol>{detail.timeline?.map(event => <li key={event.id}><time>{date(event.timestamp)}</time> · {event.action} · {event.actor}<pre>{JSON.stringify(event.details, null, 2)}</pre></li>)}</ol>
    </>}
  </main>
}

export function AdministrationPage() {
  const [users, setUsers] = useState<User[]>([])
  const [events, setEvents] = useState<Audit[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    let active = true
    Promise.all([platformApi<User[]>('/admin/users'), platformApi<Audit[]>('/admin/audit-log')])
      .then(([u, a]) => { if (active) { setUsers(u); setEvents(a) } }).catch(reason => { if (active) setError(errorText(reason)) })
    return () => { active = false }
  }, [])
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); setBusy(true)
    try { await platformApi('/admin/users', { method: 'POST', body: JSON.stringify(Object.fromEntries(data)) }); form.reset(); setUsers(await platformApi<User[]>('/admin/users')); setError('') }
    catch (reason) { setError(errorText(reason)) } finally { setBusy(false) }
  }
  return <main className="platform-page"><h1>Administration</h1>{error && <p role="alert">{error}</p>}
    <h2>Users</h2><ul>{users.map(user => <li key={user.id}>{user.username} · {user.role} · {user.enabled ? 'Enabled' : 'Disabled'}</li>)}</ul>
    <form className="platform-form" onSubmit={e => void create(e)}><label>Username<input name="username" required maxLength={128} /></label><label>Initial password<input name="password" type="password" autoComplete="new-password" minLength={12} maxLength={256} required /></label><label>Role<select name="role"><option value="viewer">Viewer</option><option value="operator">Operator</option><option value="administrator">Administrator</option></select></label><button disabled={busy}>Create user</button></form>
    <h2>Audit log</h2><div className="table-scroll"><table><thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Resource</th></tr></thead><tbody>{events.map(event => <tr key={event.id}><td>{date(event.timestamp)}</td><td>{event.actor}</td><td>{event.action}</td><td>{event.resource}</td></tr>)}</tbody></table></div>
  </main>
}
