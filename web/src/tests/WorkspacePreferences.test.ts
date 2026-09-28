import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  addSavedView,
  loadWorkspacePreferences,
  navigationCopy,
  removeSavedView,
  setWorkspaceLocale,
} from '../shared/preferences'

describe('workspace preferences', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.stubGlobal('crypto', { randomUUID: () => 'view-1' })
  })

  it('persists locale and returns localized navigation copy', () => {
    expect(loadWorkspacePreferences().locale).toBe('en')
    setWorkspaceLocale('es')
    expect(loadWorkspacePreferences().locale).toBe('es')
    expect(navigationCopy('es').incidents).toBe('Incidentes')
    expect(navigationCopy('en').incidents).toBe('Incidents')
  })

  it('stores, deduplicates and removes application deep links', () => {
    addSavedView('Payments incident', '#/incidents/inc-1')
    expect(loadWorkspacePreferences().savedViews).toEqual([
      { id: 'view-1', name: 'Payments incident', hash: '#/incidents/inc-1' },
    ])

    addSavedView('Same context', '#/incidents/inc-1')
    expect(loadWorkspacePreferences().savedViews).toHaveLength(1)
    expect(loadWorkspacePreferences().savedViews[0].name).toBe('Same context')

    removeSavedView('view-1')
    expect(loadWorkspacePreferences().savedViews).toEqual([])
  })

  it('rejects external or empty saved views and recovers from malformed storage', () => {
    expect(() => addSavedView('', '#/services')).toThrow()
    expect(() => addSavedView('External', 'https://example.com')).toThrow()
    localStorage.setItem('devicemesh.workspacePreferences.v1', '{broken')
    expect(loadWorkspacePreferences()).toEqual({ locale: 'en', savedViews: [] })
  })
})
