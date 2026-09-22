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

function quote(overrides: Record<string, unknown> = {}) {
  return {
    state: 'snapshot',
    source: 'snapshot',
    as_of: NOW,
    outcome_bids: ['0.55', '0.43'],
    outcome_asks: ['0.57', '0.45'],
    best_bid: ['ply_a', '0.55'],
    best_ask: ['ply_a', '0.57'],
    spread: '0.0200',
    depth_usd: '306.00',
    ...overrides,
  }
}

function marketSummary(overrides: Record<string, unknown> = {}) {
  return {
    market_id: 'mkt_live',
    match_id: 'mat_live',
    question: null,
    status: 'open',
    tournament_name: null,
    tier: 'atp',
    gender: 'men',
    phase: 'live',
    model_availability: 'available',
    decision_action: 'buy',
    reason_code: null,
    player_ids: ['ply_a', 'ply_b'],
    player_names: ['Alpha One', 'Beta Two'],
    model_probability: null,
    quote: quote(),
    is_stale: false,
    has_gap: false,
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
    const { rows, availability } = decodeOpportunityList({ data: [opportunity()] })
    expect(rows).toHaveLength(1)
    expect(rows[0].conservative_net_edge).toBe('0.07')
    expect(rows[0].player_names).toEqual(['Alpha One', 'Beta Two'])
    expect(rows[0].max_acceptable_price).toBeNull()
    expect(availability).toBeNull()  // older payloads stay decodable
  })

  it('accepts the wait action with a max acceptable price', () => {
    const { rows } = decodeOpportunityList({
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
        marketSummary({ question: 'Alpha One vs. Beta Two: Match Winner' }),
        marketSummary({
          market_id: 'mkt_chall',
          match_id: null,
          question: 'Challenger Moneyline',
          tier: 'challenger',
          phase: 'prematch',
          model_availability: 'out_of_scope',
          decision_action: null,
          quote: quote({ state: 'unavailable', source: null, as_of: null }),
        }),
      ],
      page: 1,
      page_size: 20,
      total: 2,
    })
    expect(page.total).toBe(2)
    expect(page.markets[0].quote.best_ask).toEqual(['ply_a', '0.57'])
    expect(page.markets[0].decision_action).toBe('buy')
    expect(page.markets[1].match_id).toBeNull()
    expect(page.markets[1].decision_action).toBeNull()
    expect(page.markets[1].model_availability).toBe('out_of_scope')
  })

  it('fails visibly on an unknown market status or tier', () => {
    const base = marketSummary({
      market_id: 'm',
      match_id: null,
      quote: quote({ state: 'unavailable', source: null, as_of: null }),
    })
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
          marketSummary({
            market_id: 'm',
            match_id: null,
            tier: null,
            gender: null,
            phase: null,
            model_availability: 'not_evaluated',
            decision_action: null,
            quote: quote({
              state: 'unavailable',
              source: null,
              as_of: null,
              best_bid: ['ply_a', '0.55', 'extra'],
              best_ask: null,
            }),
          }),
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

  it('decodes workbench enrichment: versions, gates, levels and ledger events', () => {
    const decision = decodeMatchDecision({
      data: decisionSnapshot({
        max_acceptable_price: '0.5500',
        hold_value: '10.80',
        model_version: 'prematch-elo-v1',
        calibration_version: 'platt-v1',
        policy_version: 'policy-v1',
        data_version: 'apidata-v1',
        gates: [
          { gate: 'mapping', passed: true, reason_code: null },
          { gate: 'net_edge', passed: false, reason_code: 'NO_NET_EDGE' },
        ],
        outcome_levels: [
          { player_id: 'ply_a', best_bid: '0.55', best_ask: '0.57' },
          { player_id: 'ply_b', best_bid: null, best_ask: '0.45' },
        ],
        position: {
          position_id: 'pos_1',
          outcome_player_id: 'ply_a',
          status: 'open',
          entry_cost: '10.00',
          shares: '19.05',
          average_entry_price: '0.525',
          current_exit_value: '11.40',
          net_pnl: null,
          events: [
            { id: 'e1', kind: 'entry_intent', at: NOW, reason_code: null },
            { id: 'e2', kind: 'entry_fill', at: NOW, reason_code: null },
          ],
        },
      }),
    })
    expect(decision.max_acceptable_price).toBe('0.5500')
    expect(decision.hold_value).toBe('10.80')
    expect(decision.model_version).toBe('prematch-elo-v1')
    expect(decision.data_version).toBe('apidata-v1')
    expect(decision.gates).toHaveLength(2)
    expect(decision.gates[1]).toEqual({
      gate: 'net_edge',
      passed: false,
      reason_code: 'NO_NET_EDGE',
    })
    expect(decision.outcome_levels[1].best_bid).toBeNull()
    expect(decision.position?.average_entry_price).toBe('0.525')
    expect(decision.position?.events.map((event) => event.kind)).toEqual([
      'entry_intent',
      'entry_fill',
    ])
  })

  it('tolerates snapshots without the additive workbench fields', () => {
    const decision = decodeMatchDecision({ data: decisionSnapshot() })
    expect(decision.gates).toEqual([])
    expect(decision.outcome_levels).toEqual([])
    expect(decision.max_acceptable_price).toBeNull()
    expect(decision.model_version).toBeNull()
  })

  it('fails visibly on an unknown ledger event kind or non-boolean gate', () => {
    expect(() =>
      decodeMatchDecision({
        data: decisionSnapshot({
          position: {
            position_id: 'p',
            outcome_player_id: 'ply_a',
            status: 'open',
            entry_cost: '10.00',
            shares: '19.05',
            average_entry_price: null,
            current_exit_value: null,
            net_pnl: null,
            events: [{ id: 'e', kind: 'margin_call', at: NOW, reason_code: null }],
          },
        }),
      }),
    ).toThrow(P3DecodeError)
    expect(() =>
      decodeMatchDecision({
        data: decisionSnapshot({ gates: [{ gate: 'x', passed: 'yes', reason_code: null }] }),
      }),
    ).toThrow(P3DecodeError)
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
    expect(snapshot).toEqual({
      markets: 2,
      opportunities: 1,
      open_positions: 0,
      availability: null,
    })
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

describe('T87 explicit quote, model and decision semantics', () => {
  it('decodes an explicit quote state, source and time', () => {
    const page = decodeMarketPage({
      data: [marketSummary({ model_availability: 'eligible_unpromoted', decision_action: null })],
      page: 1,
      page_size: 20,
      total: 1,
    })
    const row = page.markets[0]
    expect(row.model_availability).toBe('eligible_unpromoted')
    expect(row.decision_action).toBeNull()
    expect(row.quote.state).toBe('snapshot')
    expect(row.quote.source).toBe('snapshot')
    expect(row.quote.as_of).toBe(NOW)
  })

  it('fails visibly on an unknown quote state or source', () => {
    expect(() =>
      decodeMarketPage({
        data: [marketSummary({ quote: quote({ state: 'maybe' }) })],
        page: 1,
        page_size: 20,
        total: 1,
      }),
    ).toThrow(P3DecodeError)
    expect(() =>
      decodeMarketPage({
        data: [marketSummary({ quote: quote({ source: 'websocket' }) })],
        page: 1,
        page_size: 20,
        total: 1,
      }),
    ).toThrow(P3DecodeError)
  })

  it('fails visibly on an unknown model availability', () => {
    expect(() =>
      decodeMarketPage({
        data: [marketSummary({ model_availability: 'promoted' })],
        page: 1,
        page_size: 20,
        total: 1,
      }),
    ).toThrow(P3DecodeError)
  })

  it('decodes the opportunity availability envelope', () => {
    const { rows, availability } = decodeOpportunityList({
      data: [],
      availability: { reason: 'ELIGIBLE_UNPROMOTED', model_status: 'not_promoted' },
    })
    expect(rows).toEqual([])
    expect(availability).toEqual({
      reason: 'ELIGIBLE_UNPROMOTED',
      model_status: 'not_promoted',
    })
  })

  it('fails visibly on an unknown availability reason', () => {
    expect(() =>
      decodeOpportunityList({
        data: [],
        availability: { reason: 'MAYBE', model_status: 'unknown' },
      }),
    ).toThrow(P3DecodeError)
  })

  it('decodes the stream ready snapshot availability', () => {
    const snapshot = decodeMarketsSnapshot({
      markets: 2,
      opportunities: 0,
      open_positions: 0,
      availability: 'ELIGIBLE_UNPROMOTED',
    })
    expect(snapshot.availability).toBe('ELIGIBLE_UNPROMOTED')
    expect(decodeMarketsSnapshot({ markets: 2, opportunities: 0, open_positions: 0 }).availability).toBeNull()
  })
})

describe('T68 enriched fields', () => {
  it('decodes enriched opportunity fields', () => {
    const { rows } = decodeOpportunityList({
      data: [
        opportunity({
          player_ids: ['ply_a', 'ply_b'],
          is_stale: true,
          has_gap: false,
        }),
      ],
    })
    expect(rows[0].player_ids).toEqual(['ply_a', 'ply_b'])
    expect(rows[0].is_stale).toBe(true)
    expect(rows[0].has_gap).toBe(false)
  })

  it('fails visibly on a malformed player_ids tuple', () => {
    expect(() =>
      decodeOpportunityList({ data: [opportunity({ player_ids: ['ply_a'] })] }),
    ).toThrow(P3DecodeError)
  })

  it('decodes enriched market summary fields with per-outcome levels', () => {
    const page = decodeMarketPage({
      data: [
        marketSummary({
          market_id: 'mkt_2',
          match_id: 'mat_2',
          tournament_name: 'Test Trophy',
          tier: 'wta',
          gender: 'women',
          phase: 'prematch',
          decision_action: 'wait',
          model_probability: 0.7,
          quote: quote({
            state: 'partial',
            source: 'snapshot',
            outcome_bids: ['0.68', '0.28'],
            outcome_asks: ['0.70', null],
          }),
          is_stale: true,
        }),
      ],
      page: 1,
      page_size: 20,
      total: 1,
    })
    const row = page.markets[0]
    expect(row.tournament_name).toBe('Test Trophy')
    expect(row.quote.state).toBe('partial')
    expect(row.quote.outcome_asks).toEqual(['0.70', null])
    expect(row.quote.spread).toBe('0.0200')
    expect(row.quote.depth_usd).toBe('306.00')
    expect(row.model_probability).toBe(0.7)
    expect(row.is_stale).toBe(true)
  })

  it('fails visibly on a malformed outcome level pair or spread', () => {
    const base = marketSummary({
      market_id: 'm',
      match_id: null,
      tier: null,
      gender: null,
      phase: null,
      model_availability: 'not_evaluated',
      decision_action: null,
      player_ids: null,
      player_names: null,
      quote: quote({ outcome_asks: ['0.7'] }),
    })
    expect(() => decodeMarketPage({ data: [base], page: 1, page_size: 20, total: 1 })).toThrow(
      P3DecodeError,
    )
    expect(() =>
      decodeMarketPage({
        data: [marketSummary({ ...base, quote: quote({ spread: 'wide' }) })],
        page: 1,
        page_size: 20,
        total: 1,
      }),
    ).toThrow(P3DecodeError)
  })

  it('decodes entry_pending paper rows with average entry price', () => {
    const view = decodePaperPositions({
      open: [
        {
          position_id: 'int_entry_mat_1',
          match_id: 'mat_1',
          market_id: 'mkt_1',
          tournament_name: 'Test Open',
          outcome_player_id: 'ply_a',
          player_ids: ['ply_a', 'ply_b'],
          player_names: ['Alpha One', 'Beta Two'],
          status: 'entry_pending',
          entry_cost: '10.00',
          shares: '19.05',
          average_entry_price: '0.525',
          current_exit_value: null,
          net_pnl: null,
          freshness_as_of: NOW,
        },
      ],
      recent: [],
    })
    expect(view.open[0].status).toBe('entry_pending')
    expect(view.open[0].average_entry_price).toBe('0.525')
    expect(view.open[0].tournament_name).toBe('Test Open')
  })

  it('decodes enriched pulse rows', () => {
    const pulse = decodePulse({
      data: [
        {
          match_id: 'mat_pos',
          market_id: 'mkt_pos',
          kind: 'position',
          action: 'sell',
          phase: 'live',
          player_names: ['Alpha One', 'Beta Two'],
          model_probability: 0.6,
          executable_probability: 0.57,
          conservative_net_edge: '0.041',
          tournament_name: 'Test Open',
          is_stale: false,
          has_gap: false,
          as_of: NOW,
        },
      ],
      has_open_position: true,
    })
    expect(pulse.data[0].phase).toBe('live')
    expect(pulse.data[0].conservative_net_edge).toBe('0.041')
    expect(pulse.data[0].tournament_name).toBe('Test Open')
  })

  it('fails visibly on an unknown pulse phase', () => {
    expect(() =>
      decodePulse({
        data: [
          {
            match_id: 'm',
            market_id: null,
            kind: 'position',
            action: 'hold',
            phase: 'halftime',
            player_names: null,
            model_probability: null,
            executable_probability: null,
            conservative_net_edge: null,
            tournament_name: null,
            is_stale: false,
            has_gap: false,
            as_of: null,
          },
        ],
        has_open_position: false,
      }),
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
