// T68 view-model contract tests: DTO→row mapping is presentation-only
// (server values pass through, absent data renders '—'), and the Home pulse
// selection mirrors the server contract defensively (urgent position
// reserved, live BUY → upcoming BUY → strongest WAIT, capped at three).
import { describe, expect, it } from 'vitest'

import type {
  MarketSummaryDto,
  OpportunityDto,
  PaperPositionDto,
  PulseRowDto,
} from '@/lib/api/types'
import {
  formatFreshness,
  selectHomePulseRows,
  toMarketRow,
  toOpportunityRow,
  toPaperRow,
  toPulseRow,
  type PulseRowModel,
} from './p3-view-models'

const NOW = new Date('2026-09-16T12:00:00Z')

function opportunity(overrides: Partial<OpportunityDto> = {}): OpportunityDto {
  return {
    match_id: 'mat_1',
    market_id: 'mkt_1',
    phase: 'live',
    action: 'buy',
    target_player_id: 'ply_b',
    player_ids: ['ply_a', 'ply_b'],
    player_names: ['Alpha One', 'Beta Two'],
    model_probability: 0.62,
    executable_probability: 0.55,
    conservative_net_edge: '0.0700',
    max_acceptable_price: null,
    tournament_tier: 'atp',
    tournament_name: 'Test Open',
    is_stale: false,
    has_gap: false,
    as_of: '2026-09-16T11:59:30Z',
    ...overrides,
  }
}

function summary(overrides: Partial<MarketSummaryDto> = {}): MarketSummaryDto {
  return {
    market_id: 'mkt_1',
    match_id: 'mat_1',
    question: null,
    status: 'open',
    tournament_name: 'Test Open',
    tier: 'atp',
    gender: 'men',
    phase: 'live',
    model_availability: 'available',
    decision_action: 'buy',
    reason_code: null,
    player_ids: ['ply_a', 'ply_b'],
    player_names: ['Alpha One', 'Beta Two'],
    model_probability: 0.62,
    quote: {
      state: 'snapshot',
      source: 'snapshot',
      as_of: '2026-09-16T11:59:00Z',
      outcome_bids: ['0.55', '0.43'],
      outcome_asks: ['0.57', '0.45'],
      best_bid: ['ply_a', '0.55'],
      best_ask: ['ply_a', '0.57'],
      spread: '0.0200',
      depth_usd: '306.00',
    },
    is_stale: false,
    has_gap: false,
    as_of: '2026-09-16T11:59:00Z',
    ...overrides,
  }
}

function position(overrides: Partial<PaperPositionDto> = {}): PaperPositionDto {
  return {
    position_id: 'pos_1',
    match_id: 'mat_1',
    market_id: 'mkt_1',
    tournament_name: 'Test Open',
    outcome_player_id: 'ply_b',
    player_ids: ['ply_a', 'ply_b'],
    player_names: ['Alpha One', 'Beta Two'],
    status: 'open',
    entry_cost: '10.00',
    shares: '19.05',
    average_entry_price: '0.525',
    current_exit_value: '11.40',
    net_pnl: null,
    freshness_as_of: '2026-09-16T11:58:00Z',
    ...overrides,
  }
}

function pulseRow(overrides: Partial<PulseRowDto> = {}): PulseRowDto {
  return {
    match_id: 'mat_1',
    market_id: 'mkt_1',
    kind: 'opportunity',
    action: 'buy',
    phase: 'live',
    player_names: ['Alpha One', 'Beta Two'],
    model_probability: 0.62,
    executable_probability: 0.55,
    conservative_net_edge: '0.0700',
    tournament_name: 'Test Open',
    is_stale: false,
    has_gap: false,
    as_of: '2026-09-16T11:59:30Z',
    ...overrides,
  }
}

describe('formatFreshness', () => {
  it('formats deterministic relative text and the stale prefix', () => {
    expect(formatFreshness('2026-09-16T11:59:58Z', NOW)).toBe('刚刚')
    expect(formatFreshness('2026-09-16T11:59:18Z', NOW)).toBe('42 秒前')
    expect(formatFreshness('2026-09-16T11:47:00Z', NOW)).toBe('13 分前')
    expect(formatFreshness('2026-09-16T09:00:00Z', NOW)).toBe('3 小时前')
    expect(formatFreshness('2026-09-16T11:57:52Z', NOW, true)).toBe('最后可信 · 2 分前')
    expect(formatFreshness(null, NOW)).toBe('时间未知')
  })
})

describe('toOpportunityRow', () => {
  it('maps server values without deriving new quantities', () => {
    const row = toOpportunityRow(opportunity(), NOW)
    expect(row.match).toBe('Alpha One vs. Beta Two')
    expect(row.selection).toBe('Beta Two') // target via player_ids index
    expect(row.modelProbability).toBe(0.62)
    expect(row.edgePp).toBeCloseTo(7.0)
    expect(row.state).toBe('buy')
    expect(row.href).toBe('/matches/mat_1')
    expect(row.overlay).toBe('none')
  })

  it('keeps absent values null and stale rows overlaid', () => {
    const row = toOpportunityRow(
      opportunity({
        action: 'wait',
        conservative_net_edge: null,
        model_probability: null,
        player_names: null,
        target_player_id: null,
        is_stale: true,
        as_of: '2026-09-16T11:57:52Z',
      }),
      NOW,
    )
    expect(row.edgePp).toBeNull()
    expect(row.modelProbability).toBeNull()
    expect(row.selection).toBe('—')
    expect(row.match).toBe('— vs. —')
    expect(row.overlay).toBe('stale')
    expect(row.freshness).toContain('最后可信')
  })
})

describe('toMarketRow', () => {
  it('maps canonical enums, per-outcome levels and the quote label', () => {
    const row = toMarketRow(summary(), NOW)
    expect(row.tierLabel).toBe('ATP')
    expect(row.phase).toBe('live')
    expect(row.playerOneAsk).toBeCloseTo(0.57)
    expect(row.playerTwoAsk).toBeCloseTo(0.45)
    expect(row.spread).toBeCloseTo(0.02)
    expect(row.depth).toBeCloseTo(306)
    expect(row.decisionAction).toBe('buy')
    expect(row.quoteState).toBe('snapshot')
    expect(row.quoteLabel).toBe('快照报价 · 1 分前')
    expect(row.href).toBe('/matches/mat_1')
  })

  it('renders low-tier markets with real quotes and no negative model label', () => {
    const row = toMarketRow(
      summary({
        tier: 'challenger',
        model_availability: 'out_of_scope',
        decision_action: null,
        match_id: null,
        player_names: null,
        player_ids: null,
        question: 'Challenger Moneyline',
        model_probability: null,
        quote: {
          state: 'snapshot',
          source: 'snapshot',
          as_of: '2026-09-16T11:59:00Z',
          outcome_bids: ['0.55', '0.43'],
          outcome_asks: ['0.57', '0.45'],
          best_bid: null,
          best_ask: null,
          spread: null,
          depth_usd: null,
        },
      }),
      NOW,
    )
    expect(row.modelAvailability).toBe('out_of_scope')
    expect(row.modelAvailabilityLabel).toBeNull() // no "uncovered" label
    expect(row.decisionAction).toBeNull()
    expect(row.quoteLabel).toBe('快照报价 · 1 分前')
    expect(row.playerOneAsk).toBeCloseTo(0.57)
    expect(row.href).toBeNull() // unmapped rows are not navigable
    expect(row.match).toBe('Challenger Moneyline')
  })

  it('never invents a decision state from a null action', () => {
    const row = toMarketRow(
      summary({
        decision_action: null,
        model_availability: 'eligible_unpromoted',
        quote: {
          state: 'unavailable',
          source: null,
          as_of: null,
          outcome_bids: null,
          outcome_asks: null,
          best_bid: null,
          best_ask: null,
          spread: null,
          depth_usd: null,
        },
      }),
      NOW,
    )
    expect(row.decisionAction).toBeNull()
    expect(row.modelAvailabilityLabel).toBe('模型未晋升 · 不产生 BUY/WAIT')
    expect(row.quoteState).toBe('unavailable')
    expect(row.quoteLabel).toBe('报价暂不可用')
    expect(row.playerOneAsk).toBeNull()
  })

  it('labels every visible quote state, including a limited one', () => {
    const states = {
      realtime: '实时盘口',
      no_liquidity: '暂无挂单',
      unavailable: '报价暂不可用',
      stale: '最后可信报价已过期',
      limited: '覆盖受限 · 等待下一轮',
    } as const
    for (const [state, label] of Object.entries(states)) {
      const row = toMarketRow(
        summary({
          quote: {
            state: state as keyof typeof states,
            source: state === 'realtime' ? 'realtime' : 'snapshot',
            as_of: '2026-09-16T11:59:00Z',
            outcome_bids: null,
            outcome_asks: null,
            best_bid: null,
            best_ask: null,
            spread: null,
            depth_usd: null,
          },
        }),
        NOW,
      )
      expect(row.quoteLabel).toBe(label)
    }
  })

  it('maps closed markets and typed reason codes', () => {
    const row = toMarketRow(
      summary({
        phase: 'closed',
        status: 'closed',
        decision_action: 'no_bet',
        reason_code: 'RULE_CHANGED',
      }),
      NOW,
    )
    expect(row.phase).toBe('closed')
    expect(row.reason).toBe('规则已变更 · 动作撤销')
  })
})

describe('toPaperRow', () => {
  it('maps ledger statuses onto lifecycle labels', () => {
    expect(toPaperRow(position(), null, NOW).state).toBe('hold')
    expect(toPaperRow(position({ status: 'entry_pending' }), null, NOW).state).toBe(
      'entry_pending',
    )
    expect(toPaperRow(position({ status: 'exit_missed' }), null, NOW).state).toBe('missed')
    const row = toPaperRow(position(), 'Alpha One vs. Beta Two', NOW)
    expect(row.direction).toBe('Beta Two')
    expect(row.averageEntry).toBeCloseTo(0.525)
    expect(row.currentExitValue).toBeCloseTo(11.4)
    expect(row.netPnl).toBeNull()
  })
})

describe('selectHomePulseRows', () => {
  function model(priority: PulseRowModel['priority'], id: string): PulseRowModel {
    return {
      id,
      priority,
      match: id,
      tournament: 'T',
      phase: '直播',
      modelProbability: null,
      executableProbability: null,
      edgePp: null,
      state: 'hold',
      freshness: '刚刚',
      stale: false,
      overlay: 'none',
      href: `/matches/${id}`,
    }
  }

  it('returns zero to two candidates unchanged (capped at three)', () => {
    expect(selectHomePulseRows([])).toEqual([])
    expect(selectHomePulseRows([model('buy_live', 'a')])).toHaveLength(1)
    expect(selectHomePulseRows([model('buy_live', 'a'), model('wait', 'b')])).toHaveLength(2)
  })

  it('reserves one urgent position row and caps at three', () => {
    const selected = selectHomePulseRows([
      model('buy_live', 'b1'),
      model('position', 'p1'),
      model('buy_upcoming', 'b2'),
      model('wait', 'w1'),
      model('buy_live', 'b3'),
    ])
    // Reserved position first, then live BUYs in server order, then the
    // upcoming BUY; the WAIT is crowded out by the cap of three.
    expect(selected.map((row) => row.id)).toEqual(['p1', 'b1', 'b3'])
  })

  it('orders sell before position and buy_live → buy_upcoming → wait', () => {
    const selected = selectHomePulseRows([
      model('wait', 'w'),
      model('sell', 's'),
      model('buy_upcoming', 'u'),
      model('buy_live', 'l'),
    ])
    expect(selected.map((row) => row.id)).toEqual(['s', 'l', 'u'])
  })
})

describe('toPulseRow', () => {
  it('maps priorities and display phase labels', () => {
    expect(toPulseRow(pulseRow(), NOW).priority).toBe('buy_live')
    expect(
      toPulseRow(pulseRow({ phase: 'upcoming', match_id: 'm2' }), NOW).priority,
    ).toBe('buy_upcoming')
    expect(
      toPulseRow(pulseRow({ kind: 'position', action: 'sell', match_id: 'm3' }), NOW).priority,
    ).toBe('sell')
    expect(
      toPulseRow(pulseRow({ kind: 'position', action: 'hold', match_id: 'm4' }), NOW).priority,
    ).toBe('position')
    expect(toPulseRow(pulseRow({ phase: 'closed', match_id: 'm5' }), NOW).phase).toBe('已完赛')
    expect(toPulseRow(pulseRow(), NOW).edgePp).toBeCloseTo(7.0)
  })
})
