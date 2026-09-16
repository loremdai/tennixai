import { describe, expect, it } from 'vitest'

import {
  DECISION_STATES,
  getDecisionPreview,
  getHomePulseRows,
  marketListingFixtures,
  openPaperFixtures,
  opportunityFixtures,
  parseDecisionState,
  parseMarketView,
  parseMarketsState,
  sortHomePulseRows,
  terminalPaperFixtures,
  type DecisionState,
  type HomePulseRow,
} from './p3-preview-data'

describe('P3 preview state matrix', () => {
  it('covers every frozen decision lifecycle state', () => {
    expect(DECISION_STATES).toHaveLength(12)
    for (const state of DECISION_STATES) {
      const preview = getDecisionPreview(state, 'none', 'high', 'sinner')
      expect(preview.state).toBe(state)
      expect(preview.stateLabel).toBeTruthy()
      expect(preview.title).toBeTruthy()
    }
  })

  it('keeps trusted values while stale or gap overlays remove actions', () => {
    const stale = getDecisionPreview('buy', 'stale', 'high', 'sinner')
    const gap = getDecisionPreview('sell', 'gap', 'high', 'sinner')
    expect(stale.modelProbability).toBe(0.64)
    expect(stale.executableProbability).toBe(0.504)
    expect(stale.actionAvailable).toBe(false)
    expect(gap.actionAvailable).toBe(false)
    expect(gap.overlay).toBe('gap')
  })

  it('sorts open positions before live buy, upcoming buy, and wait', () => {
    const rows = getHomePulseRows('populated')
    expect(rows.map((row) => row.priority)).toEqual(['position', 'buy_live', 'wait'])
    const position: HomePulseRow = { ...rows[2], id: 'open', priority: 'sell', state: 'sell', stale: true }
    expect(sortHomePulseRows([...rows, position])[0].id).toBe('open')
  })

  it('keeps stale overlays on the open position without inventing a sell action', () => {
    const stalePosition = getHomePulseRows('stale').find((row) => row.id === 'pulse-position')

    expect(stalePosition).toMatchObject({
      priority: 'position',
      state: 'hold',
      stale: true,
    })
    expect(stalePosition?.href).toContain('state=hold')
    expect(stalePosition?.href).toContain('overlay=stale')
  })

  it('falls back safely for invalid URL parameters', () => {
    expect(parseDecisionState('unknown')).toBe('buy')
    expect(parseMarketView('unknown')).toBe('opportunities')
    expect(parseMarketsState('unknown')).toBe('populated')
    expect(getHomePulseRows('empty')).toHaveLength(0)
  })

  it('links every Home, Markets, and Paper fixture to its internal P3 preview state', () => {
    const homeFixtures = [
      ...getHomePulseRows('populated'),
      ...getHomePulseRows('stale').filter((fixture) => fixture.stale),
    ]
    const fixtureLinks: Array<{ id: string; href: string; expectedState: DecisionState }> = [
      ...homeFixtures.map((fixture) => ({ id: fixture.id, href: fixture.href, expectedState: fixture.state })),
      ...opportunityFixtures.map((fixture) => ({ id: fixture.id, href: fixture.href, expectedState: fixture.state })),
      ...marketListingFixtures.map((fixture) => ({ id: fixture.id, href: fixture.href, expectedState: fixture.state as DecisionState })),
      ...openPaperFixtures.map((fixture) => ({ id: fixture.id, href: fixture.href, expectedState: fixture.state })),
      ...terminalPaperFixtures.map((fixture) => ({ id: fixture.id, href: fixture.href, expectedState: fixture.state })),
    ]

    for (const { id, href, expectedState } of fixtureLinks) {
      const url = new URL(href, 'https://tennix.test')
      expect(href, id).toMatch(/^\/(?!\/)/)
      expect(url.origin, id).toBe('https://tennix.test')
      expect(url.searchParams.get('preview'), id).toBe('p3')
      const targetState = url.searchParams.get('state')
      expect(targetState, id).toBe(expectedState)
      expect(parseDecisionState(targetState ?? undefined), id).toBe(expectedState)
    }
  })
})
