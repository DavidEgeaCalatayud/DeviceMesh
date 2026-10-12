import { useEffect, useState } from 'react'
import { platformApi } from '../../shared/api/session'

type Component = {
  id: string
  label: string
  softwareStatus: string
  acceptance: string
}

type ExternalGate = {
  id: string
  label: string
  status: string
}

type Ecosystem = {
  generatedAt: string
  softwareComplete: boolean
  overallStatus: string
  components: Component[]
  externalGates: ExternalGate[]
  runtime: Record<string, number>
}

const label = (value: string) => value
  .replace(/([A-Z])/g, ' $1')
  .replace(/^./, character => character.toUpperCase())

export function EcosystemPage() {
  const [report, setReport] = useState<Ecosystem | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    platformApi<Ecosystem>('/system/ecosystem')
      .then(data => { if (active) setReport(data) })
      .catch(reason => { if (active) setError(reason instanceof Error ? reason.message : 'Request failed') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  return <main className="platform-page">
    <h1>Ecosystem readiness</h1>
    <p>One place to distinguish implemented software from acceptance evidence that requires external providers, long-running infrastructure or physical hardware.</p>
    {loading && <p role="status">Loading ecosystem readiness…</p>}
    {error && <p role="alert">{error}</p>}
    {report && <>
      <section>
        <h2>Software status</h2>
        <p><strong>{report.softwareComplete ? 'Software complete' : 'Software incomplete'}</strong> · {report.overallStatus}</p>
        <div className="platform-grid">
          {report.components.map(component => <article className="platform-card" key={component.id}>
            <h3>{component.label}</h3>
            <p>{component.softwareStatus} · {component.acceptance}</p>
          </article>)}
        </div>
      </section>
      <section>
        <h2>Runtime snapshot</h2>
        <div className="platform-grid">
          {Object.entries(report.runtime).map(([key, value]) => <article className="platform-card" key={key}>
            <h3>{label(key)}</h3><p>{value}</p>
          </article>)}
        </div>
      </section>
      <section>
        <h2>External acceptance gates</h2>
        <ul>{report.externalGates.map(gate => <li key={gate.id}><strong>{gate.label}</strong> · {gate.status}</li>)}</ul>
        <p className="muted">These gates deliberately remain separate from software readiness. DeviceMesh does not infer a 24-hour soak, store publication or physical HIL result from CI builds.</p>
      </section>
      <p className="muted">Generated {new Date(report.generatedAt).toLocaleString()}.</p>
    </>}
  </main>
}
