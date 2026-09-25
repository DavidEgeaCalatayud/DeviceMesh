export const apiBase = import.meta.env.VITE_API_BASE_URL ?? ''
const tokenKey = 'devicemesh.operatorToken'
const refreshKey = 'devicemesh.refreshToken'
export const getToken = () => sessionStorage.getItem(tokenKey) ?? ''

export async function signIn(username: string, password: string) {
  const response = await fetch(`${apiBase}/api/v1/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }),
  })
  if (!response.ok) throw new Error(response.status === 429 ? 'Too many attempts. Retry in five minutes.' : 'Sign-in failed. Check your username and password.')
  const session = await response.json() as { accessToken: string; refreshToken: string }
  sessionStorage.setItem(tokenKey, session.accessToken)
  sessionStorage.setItem(refreshKey, session.refreshToken)
}

let refreshing: Promise<boolean> | null = null
async function refreshSession(): Promise<boolean> {
  const refreshToken = sessionStorage.getItem(refreshKey)
  if (!refreshToken) return false
  const response = await fetch(`${apiBase}/api/v1/auth/refresh`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refreshToken }),
  })
  if (!response.ok) return false
  const session = await response.json() as { accessToken: string; refreshToken: string }
  sessionStorage.setItem(tokenKey, session.accessToken)
  sessionStorage.setItem(refreshKey, session.refreshToken)
  return true
}

export async function apiFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const send = () => {
    const headers = new Headers(options.headers)
    const token = getToken()
    if (token) headers.set('Authorization', `Bearer ${token}`)
    return fetch(url, { ...options, headers })
  }
  let response = await send()
  if (response.status === 401) {
    refreshing ??= refreshSession().finally(() => { refreshing = null })
    if (await refreshing) response = await send()
    if (response.status === 401) {
      sessionStorage.removeItem(tokenKey)
      sessionStorage.removeItem(refreshKey)
      window.location.hash = '#/login'
    }
  }
  return response
}

export async function signOut() {
  try { await apiFetch(`${apiBase}/api/v1/auth/logout`, { method: 'POST' }) }
  finally {
    sessionStorage.removeItem(tokenKey)
    sessionStorage.removeItem(refreshKey)
    window.location.hash = '#/login'
  }
}

export async function platformApi<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await apiFetch(`${apiBase}/api/v1${path}`, {
    ...options, headers: { 'Content-Type': 'application/json', ...options.headers },
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({})) as { detail?: string }
    throw new Error(typeof error.detail === 'string' ? error.detail : `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}
