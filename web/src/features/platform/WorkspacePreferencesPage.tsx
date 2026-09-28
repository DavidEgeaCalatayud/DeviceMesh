import { useState } from 'react'
import type { FormEvent } from 'react'
import {
  addSavedView,
  navigationCopy,
  removeSavedView,
  setWorkspaceLocale,
  useWorkspacePreferences,
  type WorkspaceLocale,
} from '../../shared/preferences'

const pageCopy = {
  en: {
    title: 'Workspace preferences', language: 'Language', english: 'English', spanish: 'Spanish',
    views: 'Saved views', description: 'Save any DeviceMesh deep link so you can return to the same operational context.',
    name: 'View name', current: 'Current route', save: 'Save current view', open: 'Open', remove: 'Remove',
    empty: 'No saved views yet.', limit: 'Up to 50 views are stored locally in this browser.',
  },
  es: {
    title: 'Preferencias del espacio de trabajo', language: 'Idioma', english: 'Inglés', spanish: 'Español',
    views: 'Vistas guardadas', description: 'Guarda cualquier enlace profundo de DeviceMesh para volver al mismo contexto operativo.',
    name: 'Nombre de la vista', current: 'Ruta actual', save: 'Guardar vista actual', open: 'Abrir', remove: 'Eliminar',
    empty: 'Todavía no hay vistas guardadas.', limit: 'Se guardan hasta 50 vistas localmente en este navegador.',
  },
} as const

export function WorkspacePreferencesPage() {
  const preferences = useWorkspacePreferences()
  const text = pageCopy[preferences.locale]
  const nav = navigationCopy(preferences.locale)
  const [name, setName] = useState('')
  const [error, setError] = useState('')

  function changeLocale(locale: WorkspaceLocale) {
    setWorkspaceLocale(locale)
    document.documentElement.lang = locale
  }

  function saveView(event: FormEvent) {
    event.preventDefault()
    setError('')
    try {
      const route = window.location.hash === '#/preferences' ? '#/' : window.location.hash || '#/'
      addSavedView(name, route)
      setName('')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to save view')
    }
  }

  return <main className="platform-page">
    <h1>{text.title}</h1>
    <section className="platform-card">
      <h2>{text.language}</h2>
      <label>{text.language}
        <select aria-label={text.language} value={preferences.locale} onChange={event => changeLocale(event.target.value as WorkspaceLocale)}>
          <option value="en">{text.english}</option>
          <option value="es">{text.spanish}</option>
        </select>
      </label>
      <p>{preferences.locale === 'es' ? 'La navegación y el espacio de operaciones usan esta preferencia.' : 'Navigation and the operator workspace use this preference.'}</p>
    </section>
    <section className="platform-card">
      <h2>{text.views}</h2>
      <p>{text.description}</p>
      <form className="platform-form" onSubmit={saveView}>
        <label>{text.name}<input value={name} maxLength={80} onChange={event => setName(event.target.value)} required /></label>
        <label>{text.current}<input value={window.location.hash === '#/preferences' ? '#/' : window.location.hash || '#/'} readOnly /></label>
        <button>{text.save}</button>
      </form>
      {error && <p role="alert">{error}</p>}
      {preferences.savedViews.length === 0 ? <p>{text.empty}</p> : <div className="compactList">
        {preferences.savedViews.map(view => <div className="compactItem" key={view.id}>
          <div><strong>{view.name}</strong><span>{view.hash}</span></div>
          <div>
            <a href={view.hash}>{text.open}</a>{' '}
            <button type="button" onClick={() => removeSavedView(view.id)}>{text.remove}</button>
          </div>
        </div>)}
      </div>}
      <p className="muted">{text.limit}</p>
    </section>
    <p className="muted">{nav.preferences}: {preferences.locale.toUpperCase()}</p>
  </main>
}
