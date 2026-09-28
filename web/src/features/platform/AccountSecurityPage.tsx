import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { apiBase, apiFetch, platformApi } from '../../shared/api/session'

type Me = { id: string; username: string; role: string; mfaEnabled: boolean }
type MfaEnrollment = { mfaCode: string; mfaEnabled: boolean; message: string }

export function AccountSecurityPage() {
  const [me, setMe] = useState<Me | null>(null)
  const [factor, setFactor] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let active = true
    platformApi<Me>('/auth/me').then(value => { if (active) setMe(value) })
      .catch(reason => { if (active) setError(reason instanceof Error ? reason.message : 'Request failed') })
    return () => { active = false }
  }, [])

  async function enableOrRotate() {
    setBusy(true); setError(''); setFactor('')
    try {
      const enrolled = await platformApi<MfaEnrollment>('/auth/mfa', { method: 'POST' })
      // The server revokes existing sessions after MFA changes. Keep the one-time
      // factor on screen instead of immediately re-authenticating and losing it.
      setMe(current => current ? { ...current, mfaEnabled: true } : current)
      setFactor(enrolled.mfaCode)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Request failed')
    } finally { setBusy(false) }
  }

  async function disable(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    setBusy(true); setError('')
    try {
      const response = await apiFetch(`${apiBase}/api/v1/auth/mfa`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mfaCode: String(data.get('mfaCode')) }),
      })
      if (!response.ok) throw new Error('Unable to disable MFA. Check the current factor.')
      setFactor('')
      // Disabling MFA revokes the current session by design.
      window.location.hash = '#/login'
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Request failed')
    } finally { setBusy(false) }
  }

  return <main className="platform-page">
    <h1>Account security</h1>
    {error && <p role="alert">{error}</p>}
    {!me && !error && <p role="status">Loading account security…</p>}
    {me && <>
      <p><strong>{me.username}</strong> · {me.role}</p>
      <section className="platform-card">
        <h2>Multi-factor authentication</h2>
        <p>Status: <strong>{me.mfaEnabled ? 'Enabled' : 'Disabled'}</strong>.</p>
        <p>DeviceMesh uses a high-entropy possession factor in addition to your password. The server stores only its SHA-256 digest.</p>
        <button disabled={busy || Boolean(factor)} onClick={() => void enableOrRotate()}>{me.mfaEnabled ? 'Rotate MFA factor' : 'Enable MFA'}</button>
        {factor && <div role="status" className="errorBanner">
          <strong>Save this factor now. It will not be shown again.</strong>
          <p><code>{factor}</code></p>
          <p>Enabling or rotating MFA revoked your existing sessions. Copy the factor, then sign in again using your password and this factor.</p>
          <a href="#/login">I saved it — sign in again</a>
        </div>}
        {me.mfaEnabled && !factor && <form className="platform-form" onSubmit={(event) => void disable(event)}>
          <label>Current MFA factor<input name="mfaCode" type="password" autoComplete="one-time-code" minLength={20} maxLength={128} required /></label>
          <button disabled={busy}>Disable MFA</button>
        </form>}
      </section>
    </>}
  </main>
}
