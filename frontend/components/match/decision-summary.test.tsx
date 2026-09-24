// T69 DecisionSummary contract: the twelve canonical states plus orthogonal
// STALE/GAP overlays, driven only by server snapshot facts (one current
// action source). Entry affordances vanish once an intent exists, and no
// copy ever claims actual wagering.
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { DecisionSummaryLive } from './decision-summary-live'
import type { DecisionSnapshotDto } from '@/lib/api/types'
import {
  STATE_LABELS,
  deriveWorkbenchState,
  toDecisionSummaryModel,
} from '@/lib/p3-workbench-models'

const NOW = new Date('2026-09-16T12:00:00Z')

function snapshot(overrides: Partial<DecisionSnapshotDto> = {}): DecisionSnapshotDto {
  return {
    match_id: 'mat_1',
    market_id: 'mkt_1',
    action: 'no_bet',
    reason_code: 'NO_NET_EDGE',
    target_player_id: 'ply_a',
    observation_version: 1,
    model_probabilities: { ply_a: 0.62, ply_b: 0.38 },
    model_availability: 'available',
    quote_average_price: null,
    quote_side: null,
    conservative_net_edge: null,
    max_acceptable_price: null,
    hold_value: null,
    model_version: 'prematch-elo-v1',
    calibration_version: 'platt-v1',
    policy_version: 'policy-v1',
    data_version: 'apidata-v1',
    gates: [],
    outcome_levels: [],
    position: null,
    lifecycle: [],
    is_stale: false,
    has_gap: false,
    lock_profit_available: false,
    as_of: '2026-09-16T11:59:30Z',
    ...overrides,
  }
}

function position(overrides: Partial<NonNullable<DecisionSnapshotDto['position']>> = {}) {
  return {
    position_id: 'pos_1',
    outcome_player_id: 'ply_a',
    status: 'open' as const,
    entry_cost: '10.00',
    shares: '19.05',
    average_entry_price: '0.525',
    current_exit_value: '11.40',
    net_pnl: null,
    events: [],
    ...overrides,
  }
}

afterEach(cleanup)

describe('deriveWorkbenchState — one current action source', () => {
  const cases: Array<[string, DecisionSnapshotDto, string]> = [
    ['market_only', snapshot({ action: 'market_only', reason_code: 'MARKET_UNMAPPED' }), 'market_only'],
    ['no_bet', snapshot({ action: 'no_bet' }), 'no_bet'],
    ['wait', snapshot({ action: 'wait', max_acceptable_price: '0.5500' }), 'wait'],
    ['buy', snapshot({ action: 'buy', conservative_net_edge: '0.0700', quote_average_price: '0.525', quote_side: 'entry' }), 'buy'],
    [
      'entry_pending',
      snapshot({ action: 'buy', lifecycle: ['entry_pending'], position: position({ status: 'entry_pending', events: [{ id: 'e', kind: 'entry_intent', at: null, reason_code: null }] }) }),
      'entry_pending',
    ],
    [
      'missed',
      snapshot({ action: 'no_bet', lifecycle: ['entry_pending', 'missed'], position: position({ status: 'missed' }) }),
      'missed',
    ],
    ['hold', snapshot({ action: 'hold', lifecycle: ['entry_pending', 'filled'], position: position() }), 'hold'],
    ['sell', snapshot({ action: 'sell', lifecycle: ['entry_pending', 'filled'], position: position() }), 'sell'],
    [
      'exit_pending',
      snapshot({ action: 'hold', lifecycle: ['entry_pending', 'filled', 'exit_pending'], position: position({ status: 'exit_pending' }) }),
      'exit_pending',
    ],
    ['exited', snapshot({ action: 'hold', lifecycle: ['entry_pending', 'filled', 'exit_pending', 'exited'], position: position({ status: 'exited' }) }), 'exited'],
    ['exit_missed', snapshot({ action: 'hold', lifecycle: ['entry_pending', 'filled', 'exit_pending', 'exit_missed'], position: position({ status: 'exit_missed' }) }), 'exit_missed'],
    ['settled', snapshot({ action: 'hold', lifecycle: ['entry_pending', 'filled', 'settled'], position: position({ status: 'settled', net_pnl: '1.40' }) }), 'settled'],
  ]

  it.each(cases)('sequences server facts into %s', (_name, input, expected) => {
    expect(deriveWorkbenchState(input)).toBe(expected)
  })

  it('never leaves the lifecycle through a stale BUY: overlay revokes actions server-side', () => {
    // The engine forbids BUY under stale/gap; a stale snapshot arrives as
    // hold/wait and the overlay is orthogonal.
    const stale = snapshot({ action: 'hold', is_stale: true, lifecycle: ['entry_pending', 'filled'], position: position() })
    expect(deriveWorkbenchState(stale)).toBe('hold')
  })
})

describe('DecisionSummaryLive', () => {
  function renderSnapshot(input: DecisionSnapshotDto) {
    const model = toDecisionSummaryModel(input, 'Alpha One', NOW)
    const view = render(<DecisionSummaryLive decision={model} onAsk={() => {}} />)
    return { model, ...view }
  }

  it('presents a simulation opportunity in plain language without developer terms', () => {
    const { model, container } = renderSnapshot(
      snapshot({
        action: 'buy',
        conservative_net_edge: '0.0700',
        quote_average_price: '0.525',
        quote_side: 'entry',
      }),
    )
    expect(model.actionAvailable).toBe(true)
    expect(screen.getAllByText('模拟买入机会')).toHaveLength(2)
    expect(screen.getAllByText('62.0%').length).toBeGreaterThanOrEqual(1) // model probability
    expect(screen.getByText('52.5%')).toBeTruthy() // $10 executable average
    expect(screen.getByText('+7.0 个百分点')).toBeTruthy()
    expect(screen.getByText('Alpha One')).toBeTruthy()
    expect(screen.getByText('10 美元模拟买入均价')).toBeTruthy()
    expect(container.textContent).not.toMatch(/P3 BETA|Paper|hard gates|freshness|NO BET|BUY|WAIT|\bedge\b/i)
    expect(screen.queryByText('$10 Paper EV')).toBeNull()
  })

  it('shows the wait cap and hides entry affordances after an intent exists', () => {
    const { model } = renderSnapshot(
      snapshot({ action: 'wait', max_acceptable_price: '0.5500' }),
    )
    expect(screen.getByText(/重新评估参考价 55.0%/)).toBeTruthy()
    // WAIT offers a price ceiling, not an entry affordance.
    expect(model.actionAvailable).toBe(false)

    cleanup()
    const buy = renderSnapshot(
      snapshot({ action: 'buy', conservative_net_edge: '0.07', quote_average_price: '0.525', quote_side: 'entry' }),
    )
    expect(buy.model.actionAvailable).toBe(true)

    cleanup()
    const pending = renderSnapshot(
      snapshot({
        action: 'buy',
        lifecycle: ['entry_pending'],
        position: position({ status: 'entry_pending' }),
      }),
    )
    // The entry affordance vanished once the intent exists.
    expect(pending.model.actionAvailable).toBe(false)
    // The only button in the summary is the conversation affordance.
    const buttons = screen.getAllByRole('button')
    expect(buttons).toHaveLength(1)
    expect(buttons[0]).toHaveTextContent('问这场比赛')
    expect(screen.getByText('等待买入确认')).toBeTruthy()
  })

  it('renders old quotes and missing updates in plain language', () => {
    renderSnapshot(
      snapshot({ action: 'hold', is_stale: true, lifecycle: ['entry_pending', 'filled'], position: position() }),
    )
    expect(screen.getByText(/市场报价更新较慢/)).toBeTruthy()
    expect(screen.getByText(/已暂停新的模拟操作/)).toBeTruthy()

    cleanup()
    renderSnapshot(
      snapshot({ action: 'wait', has_gap: true, max_acceptable_price: '0.55' }),
    )
    expect(screen.getAllByText(/比赛数据更新中断/).length).toBeGreaterThan(0)
  })

  it('keeps the state label as the single action source across all states', () => {
    for (const state of Object.keys(STATE_LABELS) as Array<keyof typeof STATE_LABELS>) {
      const input = buildStateSnapshot(state)
      const model = toDecisionSummaryModel(input, 'Alpha One', NOW)
      expect(model.state).toBe(state)
      expect(model.stateLabel).toBe(STATE_LABELS[state])
    }
  })

  it('never claims actual wagering', () => {
    const { container } = renderSnapshot(
      snapshot({ action: 'buy', conservative_net_edge: '0.07', quote_average_price: '0.525', quote_side: 'entry' }),
    )
    const text = container.textContent ?? ''
    expect(text).not.toMatch(/(?:已|已经|现在|正在)真实下单|已下注|真实买入|真实资金已|real[- ]money/i)
    expect(text).toContain('仅记录模拟交易，不会真实下单')
  })

  it('renders honest em dashes when model data is absent', () => {
    renderSnapshot(
      snapshot({
        action: 'market_only',
        reason_code: 'OUT_OF_DOMAIN',
        model_probabilities: null,
        model_availability: 'unavailable',
        target_player_id: null,
      }),
    )
    expect(screen.getAllByText('仅显示市场报价').length).toBeGreaterThan(0)
    expect(screen.getAllByText('暂未提供胜率估算，仅显示市场报价').length).toBeGreaterThan(0)
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(2)
  })

  it('does not expose an unknown internal reason code to users', () => {
    const { model, container } = renderSnapshot(
      snapshot({ reason_code: 'INTERNAL_SCORE_MISMATCH' }),
    )

    expect(model.reason).toBe('系统暂未提供更多判断原因')
    expect(container.textContent).not.toContain('INTERNAL_SCORE_MISMATCH')
  })
})

function buildStateSnapshot(state: string): DecisionSnapshotDto {
  switch (state) {
    case 'market_only':
      return snapshot({ action: 'market_only', reason_code: 'MARKET_UNMAPPED' })
    case 'no_bet':
      return snapshot({ action: 'no_bet' })
    case 'wait':
      return snapshot({ action: 'wait', max_acceptable_price: '0.55' })
    case 'buy':
      return snapshot({ action: 'buy', conservative_net_edge: '0.07', quote_average_price: '0.525', quote_side: 'entry' })
    case 'entry_pending':
      return snapshot({ action: 'buy', lifecycle: ['entry_pending'], position: position({ status: 'entry_pending' }) })
    case 'missed':
      return snapshot({ action: 'no_bet', lifecycle: ['entry_pending', 'missed'], position: position({ status: 'missed' }) })
    case 'hold':
      return snapshot({ action: 'hold', lifecycle: ['entry_pending', 'filled'], position: position() })
    case 'sell':
      return snapshot({ action: 'sell', lifecycle: ['entry_pending', 'filled'], position: position() })
    case 'exit_pending':
      return snapshot({ action: 'hold', lifecycle: ['entry_pending', 'filled', 'exit_pending'], position: position({ status: 'exit_pending' }) })
    case 'exited':
      return snapshot({ action: 'hold', lifecycle: ['entry_pending', 'filled', 'exit_pending', 'exited'], position: position({ status: 'exited' }) })
    case 'exit_missed':
      return snapshot({ action: 'hold', lifecycle: ['entry_pending', 'filled', 'exit_pending', 'exit_missed'], position: position({ status: 'exit_missed' }) })
    case 'settled':
      return snapshot({ action: 'hold', lifecycle: ['entry_pending', 'filled', 'settled'], position: position({ status: 'settled', net_pnl: '1.40' }) })
    default:
      throw new Error(`unknown state ${state}`)
  }
}
