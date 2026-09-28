import { useState } from 'react'
import type { FormEvent } from 'react'
import { signIn } from '../../shared/api/session'

const errorText = (value: unknown) => value instanceof Error ? value.message : 'Request failed'

export function SecureLoginPage() {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    setBusy(true)
    setError('')
    try {
      await signIn(
        String(data.get('username')),
        String(data.get('password')),
        String(data.get('mfaCode') ?? ''),
      )
      window.location.hash = '#/'
    } catch (reason) {
      setError(errorText(reason))
    } finally {
      setBusy(false)
    }
  }

  return <main className="platform-page">
    <h1>Sign in to DeviceMesh</h1>
    <p>Use your server account. Enter the MFA possession factor only when it is enabled for your account.</p>
    <form onSubmit={(event) => void submit(event)} className="platform-form">
      <label>Username<input name="username" autoComplete="username" required maxLength={128} /></label>
      <label>Password<input name="password" type="password" autoComplete="current-password" required maxLength={256} /></label>
      <label>MFA factor<input name="mfaCode" type="password" autoComplete="one-time-code" minLength={20} maxLength={128} /></label>
      <button disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
    </form>
    {error && <p role="alert">{error}</p>}
  </main>
}
