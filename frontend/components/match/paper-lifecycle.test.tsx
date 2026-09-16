// T69 Paper lifecycle contract: the timeline is ledger-driven — server event
// kinds map to labels in order, a superseded intent reads complete, a lone
// intent stays pending, typed no-fill reasons surface, and money cells match
// the backend decimal strings exactly (or render em dashes).
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { PaperLifecycleLive } from './paper-lifecycle-live'
import type { DecisionSnapshotDto, PositionSummaryDto } from '@/lib/api/types'
import { toPaperModel } from '@/lib/p3-workbench-models'

afterEach(cleanup)

function snapshot(position: PositionSummaryDto | null, overrides: Partial<DecisionSnapshotDto> = {}): DecisionSnapshotDto {
  return {
    match_id: 'mat_1',
    market_id: 'mkt_1',
    action: 'hold',
    reason_code: null,
    target_player_id: 'ply_a',
    observation_version: 1,
    model_probabilities: { ply_a: 0.62, ply_b: 0.38 },
    model_availability: 'available',
    quote_average_price: null,
    quote_side: null,
    conservative_net_edge: null,
    max_acceptable_price: null,
    hold_value: null,
    model_version: 'm',
    calibration_version: 'c',
    policy_version: 'p',
    data_version: 'd',
    gates: [],
    outcome_levels: [],
    position,
    lifecycle: [],
    is_stale: false,
    has_gap: false,
    lock_profit_available: false,
    as_of: '2026-09-16T11:59:30Z',
    ...overrides,
  }
}

function positionOf(overrides: Partial<PositionSummaryDto> = {}): PositionSummaryDto {
  return {
    position_id: 'pos_1',
    outcome_player_id: 'ply_a',
    status: 'open',
    entry_cost: '10.00',
    shares: '19.05',
    average_entry_price: '0.525',
    current_exit_value: '11.40',
    net_pnl: null,
    events: [],
    ...overrides,
  }
}

describe('toPaperModel', () => {
  it('maps the full ledger sequence in server order', () => {
    const model = toPaperModel(
      snapshot(
        positionOf({
          status: 'settled',
          net_pnl: '1.40',
          events: [
            { id: 'e1', kind: 'entry_intent', at: '2026-09-16T11:00:00Z', reason_code: null },
            { id: 'e2', kind: 'entry_fill', at: '2026-09-16T11:00:20Z', reason_code: null },
            { id: 'e3', kind: 'exit_intent', at: '2026-09-16T11:30:00Z', reason_code: null },
            { id: 'e4', kind: 'exit_no_fill', at: '2026-09-16T11:30:10Z', reason_code: 'PRICE_EXCEEDED' },
            { id: 'e5', kind: 'settled', at: '2026-09-16T13:00:00Z', reason_code: null },
          ],
        }),
      ),
    )
    expect(model).not.toBeNull()
    expect(model!.state).toBe('settled')
    expect(model!.events.map((event) => event.title)).toEqual([
      'Paper entry intent 已记录',
      '入场 FOK 全部成交',
      'Paper exit intent 已记录',
      '退出未成交',
      '已按市场最终 resolution 结算',
    ])
    // Superseded intents read complete; only a trailing intent stays pending.
    expect(model!.events.map((event) => event.status)).toEqual([
      'complete',
      'complete',
      'complete',
      'missed',
      'complete',
    ])
    expect(model!.events[3].detail).toContain('仓位保持开放')
    expect(model!.netPnl).toBeCloseTo(1.4)
  })

  it('keeps a lone intent pending and surfaces typed no-fill reasons', () => {
    const pending = toPaperModel(
      snapshot(
        positionOf({
          status: 'entry_pending',
          current_exit_value: null,
          events: [{ id: 'e1', kind: 'entry_intent', at: '2026-09-16T11:00:00Z', reason_code: null }],
        }),
      ),
    )
    expect(pending!.events[0].status).toBe('pending')

    const missed = toPaperModel(
      snapshot(
        positionOf({
          status: 'missed',
          events: [
            { id: 'e1', kind: 'entry_intent', at: null, reason_code: null },
            { id: 'e2', kind: 'entry_no_fill', at: null, reason_code: 'DEPTH_INSUFFICIENT' },
          ],
        }),
      ),
    )
    expect(missed!.state).toBe('missed')
    expect(missed!.events[1].status).toBe('missed')
    expect(missed!.events[1].detail).toContain('深度不足以执行 $10')
  })

  it('returns null without a ledger position', () => {
    expect(toPaperModel(snapshot(null))).toBeNull()
  })
})

describe('PaperLifecycleLive', () => {
  it('renders money cells exactly from backend decimal strings', () => {
    const model = toPaperModel(snapshot(positionOf()))!
    render(<PaperLifecycleLive paper={model} />)
    expect(screen.getByText('$10.00 · 52.5%')).toBeTruthy()
    expect(screen.getByText('19.05')).toBeTruthy()
    expect(screen.getByText('$11.40')).toBeTruthy()
    expect(screen.getByText('—')).toBeTruthy() // net P&L unset until settlement
    expect(screen.getByText('FILLED / HOLD')).toBeTruthy()
  })

  it('renders em dashes for pending intents without fabricating a position', () => {
    const model = toPaperModel(
      snapshot(
        positionOf({
          status: 'entry_pending',
          current_exit_value: null,
          events: [{ id: 'e1', kind: 'entry_intent', at: '2026-09-16T11:00:00Z', reason_code: null }],
        }),
      ),
    )!
    render(<PaperLifecycleLive paper={model} />)
    expect(screen.getByText('ENTRY PENDING')).toBeTruthy()
    // shares / current value / net P&L stay em-dashed before a fill.
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(3)
    expect(screen.getByText('Paper entry intent 已记录')).toBeTruthy()
  })

  it('never claims real wagering in the ledger copy', () => {
    const model = toPaperModel(snapshot(positionOf()))!
    const { container } = render(<PaperLifecycleLive paper={model} />)
    expect(container.textContent).not.toMatch(/真实下单|已下注|真实买入|real[- ]money/i)
  })
})
