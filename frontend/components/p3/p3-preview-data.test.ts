import { describe, expect, it } from 'vitest'

import {
  DECISION_STATES,
  getDecisionPreview,
  getHomePulseRows,
  parseDecisionState,
  parseMarketView,
  parseMarketsState,
  sortHomePulseRows,
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

  it('falls back safely for invalid URL parameters', () => {
    expect(parseDecisionState('unknown')).toBe('buy')
    expect(parseMarketView('unknown')).toBe('opportunities')
    expect(parseMarketsState('unknown')).toBe('populated')
    expect(getHomePulseRows('empty')).toHaveLength(0)
  })
})
