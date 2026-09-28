import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { platformApi } from '../../shared/api/session'

type Me = { id: string; username: string; role: string; mfaEnabled: boolean }
type MfaEnrollment = { mfaCode: string; mfaEnabled: boolean; message: string }

export function AccountSecurityPage() {
  const [me, setMe] = useState<Me | null>(null)
  const [factor, setFactor] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function load() {
    setMe(await platformApi<Me>('/auth/me'))
  }

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
      setFactor(enrolled.mfaCode)
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Request failed')
    } finally { setBusy(false) }
  }

  async function disable(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    setBusy(true); setError('')
    try {
      await platformApi('/auth/mfa', {
        method: 'DELETE',
        body: JSON.stringify({ mfaCode: String(data.get('mfaCode')) }),
      })
      setFactor('')
      await load()
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
        <button disabled={busy} onClick={() => void enableOrRotate()}>{me.mfaEnabled ? 'Rotate MFA factor' : 'Enable MFA'}</button>
        {factor && <div role="status" className="errorBanner">
          <strong>Save this factor now. It will not be shown again.</strong>
          <p><code>{factor}</code></p>
          <p>Enabling or rotating MFA revokes your existing sessions. Sign in again using your password and this factor.</p>
        </div>}
        {me.mfaEnabled && <form className="platform-form" onSubmit={(event) => void disable(event)}>
          <label>Current MFA factor<input name="mfaCode" type="password" autoComplete="one-time-code" minLength={20} maxLength={128} required /></label>
          <button disabled={busy}>Disable MFA</button>
        </form>}
      </section>
    </>}
  </main>
}
