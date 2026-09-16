// Runtime decoding tests for every P3 DTO and SSE event discriminator (T67).
// Unknown enums must fail visibly (P3DecodeError) instead of being coerced;
// nullable fields stay honestly null; decimal payloads stay strings.
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

import {
  P3DecodeError,
  decodeDecisionStreamEvent,
  decodeMarketPage,
  decodeMarketStreamEvent,
  decodeMarketsSnapshot,
  decodeMatchDecision,
  decodeOpportunityList,
  decodePaperPositions,
  decodePulse,
} from './p3-types'

const NOW = '2026-09-16T12:00:00Z'

function opportunity(overrides: Record<string, unknown> = {}) {
  return {
    match_id: 'mat_live',
    market_id: 'mkt_live',
    phase: 'live',
    action: 'buy',
    target_player_id: 'ply_a',
    player_names: ['Alpha One', 'Beta Two'],
    model_probability: 0.62,
    executable_probability: 0.55,
    conservative_net_edge: '0.07',
    max_acceptable_price: null,
    tournament_tier: 'atp',
    tournament_name: 'Test Open',
    as_of: NOW,
    ...overrides,
  }
}

function decisionSnapshot(overrides: Record<string, unknown> = {}) {
  return {
    match_id: 'mat_9',
    market_id: 'mkt_9',
    action: 'hold',
    reason_code: null,
    observation_version: 7,
    model_probabilities: { ply_a: 0.55, ply_b: 0.45 },
    model_availability: 'available',
    quote_average_price: null,
    quote_side: null,
    conservative_net_edge: null,
    position: null,
    lifecycle: ['entry_pending', 'filled'],
    is_stale: false,
    has_gap: false,
    lock_profit_available: false,
    as_of: NOW,
    ...overrides,
  }
}

describe('P3 DTO decoding', () => {
  it('decodes a valid opportunity list and keeps decimals as strings', () => {
    const rows = decodeOpportunityList({ data: [opportunity()] })
    expect(rows).toHaveLength(1)
    expect(rows[0].conservative_net_edge).toBe('0.07')
    expect(rows[0].player_names).toEqual(['Alpha One', 'Beta Two'])
    expect(rows[0].max_acceptable_price).toBeNull()
  })

  it('accepts the wait action with a max acceptable price', () => {
    const rows = decodeOpportunityList({
      data: [opportunity({ action: 'wait', max_acceptable_price: '0.5500', conservative_net_edge: null })],
    })
    expect(rows[0].action).toBe('wait')
    expect(rows[0].max_acceptable_price).toBe('0.5500')
  })

  it('fails visibly on an unknown opportunity action instead of coercing', () => {
    expect(() => decodeOpportunityList({ data: [opportunity({ action: 'short' })] })).toThrow(P3DecodeError)
  })

  it('fails visibly on an unknown opportunity phase', () => {
    expect(() => decodeOpportunityList({ data: [opportunity({ phase: 'inplay' })] })).toThrow(P3DecodeError)
  })

  it('fails visibly on a malformed decimal string', () => {
    expect(() => decodeOpportunityList({ data: [opportunity({ conservative_net_edge: 'edge' })] })).toThrow(
      P3DecodeError,
    )
  })

  it('decodes the market page envelope with canonical filters', () => {
    const page = decodeMarketPage({
      data: [
        {
          market_id: 'mkt_live',
          match_id: 'mat_live',
          question: 'Alpha One vs. Beta Two: Match Winner',
          status: 'open',
          tier: 'atp',
          gender: 'men',
          phase: 'live',
          model_covered: true,
          action: 'buy',
          reason_code: null,
          best_bid: ['ply_a', '0.55'],
          best_ask: ['ply_a', '0.57'],
          as_of: NOW,
        },
        {
          market_id: 'mkt_chall',
          match_id: null,
          question: 'Challenger Moneyline',
          status: 'open',
          tier: 'challenger',
          gender: 'men',
          phase: 'prematch',
          model_covered: false,
          action: 'market_only',
          reason_code: null,
          best_bid: null,
          best_ask: null,
          as_of: NOW,
        },
      ],
      page: 1,
      page_size: 20,
      total: 2,
    })
    expect(page.total).toBe(2)
    expect(page.markets[0].best_ask).toEqual(['ply_a', '0.57'])
    expect(page.markets[1].match_id).toBeNull()
  })

  it('fails visibly on an unknown market status or tier', () => {
    const base = {
      market_id: 'm',
      match_id: null,
      question: null,
      status: 'open',
      tier: 'atp',
      gender: 'men',
      phase: 'live',
      model_covered: false,
      action: null,
      reason_code: null,
      best_bid: null,
      best_ask: null,
      as_of: null,
    }
    expect(() => decodeMarketPage({ data: [{ ...base, status: 'paused' }], page: 1, page_size: 20, total: 1 })).toThrow(
      P3DecodeError,
    )
    expect(() => decodeMarketPage({ data: [{ ...base, tier: 'futures' }], page: 1, page_size: 20, total: 1 })).toThrow(
      P3DecodeError,
    )
  })

  it('fails visibly on a malformed best_bid tuple', () => {
    expect(() =>
      decodeMarketPage({
        data: [
          {
            market_id: 'm',
            match_id: null,
            question: null,
            status: 'open',
            tier: null,
            gender: null,
            phase: null,
            model_covered: false,
            action: null,
            reason_code: null,
            best_bid: ['ply_a', '0.55', 'extra'],
            best_ask: null,
            as_of: null,
          },
        ],
        page: 1,
        page_size: 20,
        total: 1,
      }),
    ).toThrow(P3DecodeError)
  })

  it('decodes paper positions with open and recent buckets', () => {
    const view = decodePaperPositions({
      open: [
        {
          position_id: 'pos_1',
          match_id: 'mat_pos',
          market_id: 'mkt_pos',
          outcome_player_id: 'ply_a',
          player_names: ['Alpha One', 'Beta Two'],
          status: 'open',
          entry_cost: '10.00',
          shares: '19.05',
          current_exit_value: '11.40',
          net_pnl: null,
          freshness_as_of: NOW,
        },
      ],
      recent: [
        {
          position_id: 'pos_0',
          match_id: 'mat_old',
          market_id: 'mkt_old',
          outcome_player_id: 'ply_b',
          player_names: null,
          status: 'settled',
          entry_cost: '10.00',
          shares: '19.05',
          current_exit_value: null,
          net_pnl: '1.40',
          freshness_as_of: NOW,
        },
      ],
    })
    expect(view.open[0].status).toBe('open')
    expect(view.recent[0].net_pnl).toBe('1.40')
  })

  it('fails visibly on an unknown position status', () => {
    expect(() =>
      decodePaperPositions({
        open: [
          {
            position_id: 'pos_1',
            match_id: 'm',
            market_id: 'k',
            outcome_player_id: 'ply_a',
            player_names: null,
            status: 'liquidated',
            entry_cost: '10.00',
            shares: '19.05',
            current_exit_value: null,
            net_pnl: null,
            freshness_as_of: null,
          },
        ],
        recent: [],
      }),
    ).toThrow(P3DecodeError)
  })

  it('decodes the pulse envelope and caps nothing (server already caps)', () => {
    const pulse = decodePulse({
      data: [
        {
          match_id: 'mat_pos',
          market_id: 'mkt_pos',
          kind: 'position',
          action: 'hold',
          player_names: ['Alpha One', 'Beta Two'],
          model_probability: 0.6,
          executable_probability: 0.57,
          as_of: NOW,
        },
      ],
      has_open_position: true,
    })
    expect(pulse.has_open_position).toBe(true)
    expect(pulse.data[0].kind).toBe('position')
  })

  it('fails visibly on an unknown pulse kind', () => {
    expect(() =>
      decodePulse({
        data: [
          {
            match_id: 'm',
            market_id: null,
            kind: 'rumor',
            action: 'hold',
            player_names: null,
            model_probability: null,
            executable_probability: null,
            as_of: null,
          },
        ],
        has_open_position: false,
      }),
    ).toThrow(P3DecodeError)
  })

  it('decodes a full match decision snapshot', () => {
    const decision = decodeMatchDecision({
      data: decisionSnapshot({
        position: {
          position_id: 'pos_1',
          outcome_player_id: 'ply_a',
          status: 'open',
          entry_cost: '10.00',
          shares: '19.05',
        },
      }),
    })
    expect(decision.observation_version).toBe(7)
    expect(decision.lifecycle).toEqual(['entry_pending', 'filled'])
    expect(decision.position?.status).toBe('open')
  })

  it('fails visibly on an unknown lifecycle state or decision action', () => {
    expect(() => decodeMatchDecision({ data: decisionSnapshot({ lifecycle: ['entry_pending', 'reentered'] }) })).toThrow(
      P3DecodeError,
    )
    expect(() => decodeMatchDecision({ data: decisionSnapshot({ action: 'double_down' }) })).toThrow(P3DecodeError)
  })

  it('fails visibly on an out-of-range model probability', () => {
    expect(() =>
      decodeMatchDecision({ data: decisionSnapshot({ model_probabilities: { ply_a: 1.5 } }) }),
    ).toThrow(P3DecodeError)
  })

  it('decodes the markets snapshot counters', () => {
    const snapshot = decodeMarketsSnapshot({ markets: 2, opportunities: 1, open_positions: 0 })
    expect(snapshot).toEqual({ markets: 2, opportunities: 1, open_positions: 0 })
    expect(() => decodeMarketsSnapshot({ markets: -1, opportunities: 0, open_positions: 0 })).toThrow(P3DecodeError)
  })
})

describe('market stream event discriminators', () => {
  it('decodes ready with the snapshot counters', () => {
    const event = decodeMarketStreamEvent('ready', { markets: 1, opportunities: 0, open_positions: 0 })
    expect(event.type).toBe('ready')
  })

  it('decodes market_delta with its own sequence cursor', () => {
    const event = decodeMarketStreamEvent('market_delta', {
      type: 'market_delta',
      market_id: 'mkt_1',
      sequence: 12,
      book_hash: 'h12',
      as_of: NOW,
    })
    expect(event.type).toBe('market_delta')
    if (event.type === 'market_delta') {
      expect(event.payload.sequence).toBe(12)
    }
  })

  it('decodes market_gap, decision_delta, paper_delta and resolution_delta', () => {
    expect(
      decodeMarketStreamEvent('market_gap', { market_id: 'mkt_1', reason: 'reconnect', as_of: NOW }).type,
    ).toBe('market_gap')
    expect(
      decodeMarketStreamEvent('decision_delta', {
        match_id: 'mat_1',
        observation_version: 5,
        action: 'wait',
        as_of: NOW,
      }).type,
    ).toBe('decision_delta')
    const paper = decodeMarketStreamEvent('paper_delta', {
      state: 'filled',
      id: 'mat_1',
      reason: null,
      as_of: NOW,
    })
    expect(paper.type).toBe('paper_delta')
    const resolution = decodeMarketStreamEvent('resolution_delta', {
      market_id: 'mkt_1',
      status: 'final',
      rules_version: 2,
      payouts: [
        { player_id: 'ply_a', payout_per_share: '1' },
        { player_id: 'ply_b', payout_per_share: '0' },
      ],
      confirmed_at: NOW,
    })
    expect(resolution.type).toBe('resolution_delta')
  })

  it('decodes heartbeat with an empty payload', () => {
    expect(decodeMarketStreamEvent('heartbeat', {}).type).toBe('heartbeat')
  })

  it('fails visibly on an unknown event discriminator', () => {
    expect(() => decodeMarketStreamEvent('odds_delta', { market_id: 'm' })).toThrow(P3DecodeError)
  })

  it('fails visibly on malformed delta payloads', () => {
    expect(() => decodeMarketStreamEvent('market_delta', { market_id: 'mkt_1' })).toThrow(P3DecodeError)
    expect(() =>
      decodeMarketStreamEvent('decision_delta', { match_id: 'm', observation_version: 1, action: 'yolo', as_of: NOW }),
    ).toThrow(P3DecodeError)
    expect(() => decodeMarketStreamEvent('paper_delta', { state: 'rekt', id: 'm', as_of: NOW })).toThrow(
      P3DecodeError,
    )
    expect(() => decodeMarketStreamEvent('resolution_delta', { market_id: 'm', status: 'maybe' })).toThrow(
      P3DecodeError,
    )
  })
})

describe('decision stream event discriminators', () => {
  it('decodes ready with a null decision for unknown matches', () => {
    const event = decodeDecisionStreamEvent('ready', {
      match_id: 'mat_missing',
      decision: null,
      observation_version: 0,
      action: null,
    })
    expect(event.type).toBe('ready')
    if (event.type === 'ready') {
      expect(event.payload.decision).toBeNull()
    }
  })

  it('decodes ready with a full decision snapshot', () => {
    const event = decodeDecisionStreamEvent('ready', {
      match_id: 'mat_9',
      decision: decisionSnapshot(),
      observation_version: 7,
      action: 'hold',
    })
    expect(event.type).toBe('ready')
  })

  it('decodes decision_delta and heartbeat', () => {
    expect(
      decodeDecisionStreamEvent('decision_delta', {
        match_id: 'mat_9',
        observation_version: 8,
        action: 'buy',
        as_of: NOW,
      }).type,
    ).toBe('decision_delta')
    expect(decodeDecisionStreamEvent('heartbeat', {}).type).toBe('heartbeat')
  })

  it('fails visibly on an unknown discriminator or a market-only event', () => {
    expect(() => decodeDecisionStreamEvent('paper_delta', { state: 'filled', id: 'm' })).toThrow(P3DecodeError)
    expect(() =>
      decodeDecisionStreamEvent('decision_delta', { match_id: 'm', observation_version: 'x', action: 'buy' }),
    ).toThrow(P3DecodeError)
  })
})

describe('transport isolation from preview data', () => {
  it('production transport files never import p3-preview-data', () => {
    const files = [
      'lib/api/client.ts',
      'lib/api/p3-types.ts',
      'hooks/use-market-stream.ts',
      'hooks/use-decision-stream.ts',
    ]
    for (const file of files) {
      const source = readFileSync(join(process.cwd(), file), 'utf8')
      expect(source, file).not.toContain('p3-preview-data')
    }
  })
})
