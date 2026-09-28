import { useEffect, useState } from 'react'

export type WorkspaceLocale = 'en' | 'es'
export type SavedView = { id: string; name: string; hash: string }

type WorkspacePreferences = {
  locale: WorkspaceLocale
  savedViews: SavedView[]
}

const storageKey = 'devicemesh.workspacePreferences.v1'
const eventName = 'devicemesh:workspace-preferences'
const defaults: WorkspacePreferences = { locale: 'en', savedViews: [] }

function normalize(value: unknown): WorkspacePreferences {
  if (!value || typeof value !== 'object') return defaults
  const raw = value as Partial<WorkspacePreferences>
  const locale: WorkspaceLocale = raw.locale === 'es' ? 'es' : 'en'
  const savedViews = Array.isArray(raw.savedViews)
    ? raw.savedViews.filter((view): view is SavedView => Boolean(
      view && typeof view.id === 'string' && typeof view.name === 'string' && typeof view.hash === 'string'
      && view.hash.startsWith('#/'),
    )).slice(0, 50)
    : []
  return { locale, savedViews }
}

export function loadWorkspacePreferences(): WorkspacePreferences {
  try {
    return normalize(JSON.parse(localStorage.getItem(storageKey) ?? 'null'))
  } catch {
    return defaults
  }
}

function save(next: WorkspacePreferences): void {
  localStorage.setItem(storageKey, JSON.stringify(next))
  window.dispatchEvent(new CustomEvent(eventName))
}

export function setWorkspaceLocale(locale: WorkspaceLocale): void {
  save({ ...loadWorkspacePreferences(), locale })
}

export function addSavedView(name: string, hash: string): SavedView {
  const trimmed = name.trim().slice(0, 80)
  if (!trimmed) throw new Error('A saved view needs a name.')
  if (!hash.startsWith('#/')) throw new Error('Only DeviceMesh application routes can be saved.')
  const view: SavedView = {
    id: globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    name: trimmed,
    hash,
  }
  const current = loadWorkspacePreferences()
  save({ ...current, savedViews: [view, ...current.savedViews.filter(item => item.hash !== hash)].slice(0, 50) })
  return view
}

export function removeSavedView(id: string): void {
  const current = loadWorkspacePreferences()
  save({ ...current, savedViews: current.savedViews.filter(view => view.id !== id) })
}

export function useWorkspacePreferences(): WorkspacePreferences {
  const [preferences, setPreferences] = useState(loadWorkspacePreferences)
  useEffect(() => {
    const refresh = () => setPreferences(loadWorkspacePreferences())
    window.addEventListener(eventName, refresh)
    window.addEventListener('storage', refresh)
    return () => {
      window.removeEventListener(eventName, refresh)
      window.removeEventListener('storage', refresh)
    }
  }, [])
  return preferences
}

const copy = {
  en: {
    overview: 'Overview', services: 'Services', incidents: 'Incidents', maintenance: 'Maintenance',
    operations: 'Operations', synthetics: 'Synthetics', probes: 'Probes', administration: 'Administration',
    audit: 'Audit', preferences: 'Preferences', security: 'Account security', signIn: 'Sign in', signOut: 'Sign out',
  },
  es: {
    overview: 'Resumen', services: 'Servicios', incidents: 'Incidentes', maintenance: 'Mantenimiento',
    operations: 'Operaciones', synthetics: 'Sintéticos', probes: 'Sondas', administration: 'Administración',
    audit: 'Auditoría', preferences: 'Preferencias', security: 'Seguridad de la cuenta', signIn: 'Iniciar sesión', signOut: 'Cerrar sesión',
  },
} as const

export function navigationCopy(locale: WorkspaceLocale) {
  return copy[locale]
}
