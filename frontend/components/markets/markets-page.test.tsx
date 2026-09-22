import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { MarketsPage } from './markets-page'

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

afterEach(cleanup)

describe('P3 markets preview', () => {
  it('exposes the three frozen views and switches their panels', async () => {
    const user = userEvent.setup()
    render(
      <MarketsPage
        initialView="opportunities"
        initialState="populated"
        initialTiers={[]}
        initialGender="all"
        initialPhase="all"
      />,
    )

    const tabs = screen.getAllByRole('tab')
    expect(tabs).toHaveLength(3)
    expect(tabs.map((tab) => tab.textContent)).toEqual(['机会BUY 与 WAIT', '全部市场覆盖与 market-only', 'Paper生命周期账本'])
    expect(screen.getByRole('tabpanel')).toHaveAttribute('id', 'markets-panel-opportunities')

    await user.click(screen.getByRole('tab', { name: /全部市场/ }))
    expect(screen.getByRole('tabpanel')).toHaveAttribute('id', 'markets-panel-all')
    expect(screen.getByText('市场筛选')).toBeVisible()

    await user.click(screen.getByRole('tab', { name: /^Paper/ }))
    expect(screen.getByRole('tabpanel')).toHaveAttribute('id', 'markets-panel-paper')
    expect(screen.getByText('Paper 生命周期账本')).toBeVisible()
  })

  it('keeps market rows internal and exposes no wallet or real-trade control', () => {
    render(
      <MarketsPage
        initialView="all"
        initialState="populated"
        initialTiers={[]}
        initialGender="all"
        initialPhase="all"
      />,
    )

    for (const link of screen.getAllByRole('link')) {
      expect(link.getAttribute('href')).toMatch(/^\/(?!\/)/)
    }
    expect(screen.queryAllByRole('button', { name: /钱包|下单|真实交易/ })).toHaveLength(0)
  })

})

// ---------------------------------------------------------------------------
// T68: production workspace on canonical APIs (no preview fixtures).
// ---------------------------------------------------------------------------

import { MarketsWorkspace } from './markets-state'
import { waitFor } from '@testing-library/react'
import type {
  MarketSummaryDto,
  OpportunityAvailabilityReason,
  OpportunityDto,
  PaperPositionDto,
} from '@/lib/api/types'

const {
  listMarketOpportunitiesMock,
  listMarketsMock,
  getPaperPositionsMock,
} = vi.hoisted(() => ({
  listMarketOpportunitiesMock: vi.fn(),
  listMarketsMock: vi.fn(),
  getPaperPositionsMock: vi.fn(),
}))

vi.mock('@/lib/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api/client')>()
  return {
    ...actual,
    listMarketOpportunities: listMarketOpportunitiesMock,
    listMarkets: listMarketsMock,
    getPaperPositions: getPaperPositionsMock,
  }
})

vi.mock('@/hooks/use-market-stream', () => ({
  useMarketStream: () => ({
    snapshot: null,
    books: {},
    decisions: {},
    paper: {},
    resolutions: {},
    gaps: [],
    phase: 'live',
    errorCode: null,
    lastEventId: null,
    refresh: async () => {},
  }),
}))

const AS_OF = '2026-09-16T11:59:30Z'

function opportunityDto(overrides: Partial<OpportunityDto> = {}): OpportunityDto {
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
    as_of: AS_OF,
    ...overrides,
  }
}

function quoteDto(
  overrides: Partial<MarketSummaryDto['quote']> = {},
): MarketSummaryDto['quote'] {
  return {
    state: 'snapshot',
    source: 'snapshot',
    as_of: AS_OF,
    outcome_bids: ['0.55', '0.43'],
    outcome_asks: ['0.57', '0.45'],
    best_bid: ['ply_a', '0.55'],
    best_ask: ['ply_a', '0.57'],
    spread: '0.0200',
    depth_usd: '306.00',
    ...overrides,
  }
}

function summaryDto(overrides: Partial<MarketSummaryDto> = {}): MarketSummaryDto {
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
    quote: quoteDto(),
    is_stale: false,
    has_gap: false,
    as_of: AS_OF,
    ...overrides,
  }
}

function positionDto(overrides: Partial<PaperPositionDto> = {}): PaperPositionDto {
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
    freshness_as_of: AS_OF,
    ...overrides,
  }
}

function mockWorkspaceData() {
  listMarketOpportunitiesMock.mockResolvedValue({
    rows: [opportunityDto()],
    availability: { reason: 'HAS_OPPORTUNITIES', model_status: 'unknown' },
  })
  listMarketsMock.mockResolvedValue({
    markets: [summaryDto()],
    page: 1,
    page_size: 50,
    total: 1,
  })
  getPaperPositionsMock.mockResolvedValue({ open: [positionDto()], recent: [] })
}

async function apiError(status: number, code: string) {
  const { ApiError } = await import('@/lib/api/client')
  return new ApiError(status, code, code)
}

describe('MarketsWorkspace (production)', () => {
  beforeEach(() => {
    mockWorkspaceData()
  })

  it('renders opportunities from the canonical API in server order', async () => {
    listMarketOpportunitiesMock.mockResolvedValue({
      rows: [
      opportunityDto(),
      opportunityDto({
        match_id: 'mat_2',
        phase: 'upcoming',
        action: 'wait',
        conservative_net_edge: null,
        max_acceptable_price: '0.5500',
        player_names: ['Gamma Three', 'Delta Four'],
        target_player_id: 'ply_a',
        player_ids: ['ply_a', 'ply_c'],
      }),
      ],
      availability: { reason: 'HAS_OPPORTUNITIES', model_status: 'unknown' },
    })
    const user = userEvent.setup()
    render(<MarketsWorkspace />)

    await waitFor(() => expect(screen.getByText('Alpha One vs. Beta Two')).toBeTruthy())
    const rows = screen.getAllByRole('link', { name: /查看 .* 的 (buy|wait) 决策/ })
    expect(rows.map((row) => row.getAttribute('href'))).toEqual([
      '/matches/mat_1',
      '/matches/mat_2',
    ])
    expect(screen.getByText('方向：Beta Two')).toBeTruthy()
    expect(screen.getByText('方向：Gamma Three')).toBeTruthy()
    expect(screen.getByText('+7.0pp')).toBeTruthy()
    expect(screen.getByText('最高价 55.0%')).toBeTruthy()
  })

  it('keeps every row link internal and exposes no trade buttons', async () => {
    const user = userEvent.setup()
    render(<MarketsWorkspace />)
    await waitFor(() => expect(screen.getByText('Alpha One vs. Beta Two')).toBeTruthy())

    for (const link of screen.getAllByRole('link')) {
      const href = link.getAttribute('href') ?? ''
      if (href.startsWith('http')) continue
      expect(href).toMatch(/^\/(?!\/)/)
    }
    expect(
      screen.queryAllByRole('button', { name: /BUY|SELL|钱包|下单|真实交易/ }),
    ).toHaveLength(0)
    await user.click(screen.getByRole('tab', { name: /Paper/ }))
    expect(
      screen.queryAllByRole('button', { name: /BUY|SELL|钱包|下单|真实交易/ }),
    ).toHaveLength(0)
  })

  it('shows challenger market-only rows without negative labels', async () => {
    listMarketsMock.mockResolvedValue({
      markets: [
        summaryDto({
          market_id: 'mkt_c',
          match_id: null,
          question: 'Challenger Moneyline',
          tier: 'challenger',
          model_availability: 'out_of_scope',
          decision_action: null,
          player_ids: null,
          player_names: null,
          model_probability: null,
          quote: quoteDto({
            state: 'partial',
            outcome_bids: null,
            outcome_asks: ['0.57', null],
            spread: null,
            depth_usd: null,
          }),
        }),
      ],
      page: 1,
      page_size: 50,
      total: 1,
    })
    const user = userEvent.setup()
    render(<MarketsWorkspace />)
    await user.click(screen.getByRole('tab', { name: /全部市场/ }))

    await waitFor(() => expect(screen.getByText('Challenger Moneyline')).toBeTruthy())
    // The row states its real quote state, not an invented MARKET_ONLY.
    expect(screen.getByText(/部分报价 ·/)).toBeTruthy()
    expect(screen.queryByText('不伪造模型值')).toBeNull()
    expect(screen.queryByText(/不支持|unsupported|uncovered|未覆盖/)).toBeNull()
    // Incomplete book → honest em dash, never a fabricated zero.
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(2)
    // Unmapped rows are not navigable.
    expect(
      screen.queryByRole('link', { name: '查看 Challenger Moneyline 市场' }),
    ).toBeNull()
  })

  it('applies canonical filters to server rows', async () => {
    listMarketsMock.mockResolvedValue({
      markets: [
        summaryDto(),
        summaryDto({
          market_id: 'mkt_w',
          match_id: 'mat_w',
          tier: 'wta',
          gender: 'women',
          phase: 'prematch',
          decision_action: null,
        }),
      ],
      page: 1,
      page_size: 50,
      total: 2,
    })
    const user = userEvent.setup()
    render(<MarketsWorkspace />)
    await user.click(screen.getByRole('tab', { name: /全部市场/ }))
    await waitFor(() =>
      expect(screen.getAllByRole('link', { name: /查看 .* 市场/ })).toHaveLength(2),
    )

    await user.click(screen.getByRole('button', { name: 'WTA' }))
    await waitFor(() =>
      expect(screen.getAllByRole('link', { name: /查看 .* 市场/ })).toHaveLength(1),
    )
    expect(window.location.search).toContain('tier=wta')

    await user.click(screen.getByRole('button', { name: '重置' }))
    await waitFor(() =>
      expect(screen.getAllByRole('link', { name: /查看 .* 市场/ })).toHaveLength(2),
    )
  })

  it('renders the paper ledger from the ledger with lifecycle priority', async () => {
    getPaperPositionsMock.mockResolvedValue({
      open: [
        positionDto({ position_id: 'int_entry_mat_2', match_id: 'mat_2', status: 'entry_pending' }),
        positionDto(),
      ],
      recent: [
        positionDto({
          position_id: 'pos_0',
          match_id: 'mat_0',
          status: 'settled',
          current_exit_value: null,
          net_pnl: '1.40',
        }),
      ],
    })
    const user = userEvent.setup()
    render(<MarketsWorkspace />)
    await user.click(screen.getByRole('tab', { name: /^Paper/ }))

    await waitFor(() => expect(screen.getByText('Paper 生命周期账本')).toBeTruthy())
    expect(screen.getByText('3 条')).toBeTruthy()
    const badges = screen.getAllByText(/FILLED \/ HOLD|ENTRY PENDING|SETTLED/)
    expect(badges.map((badge) => badge.textContent)).toEqual([
      'FILLED / HOLD',
      'ENTRY PENDING',
      'SETTLED',
    ])
    expect(screen.getAllByText('$10.00 · 52.5%')).toHaveLength(3)
    expect(screen.getByText('+$1.40')).toBeTruthy()
    expect(screen.queryByText(/钱包|下单|真实交易/)).toBeNull()
  })

  it('shows a loading skeleton before data arrives', async () => {
    listMarketOpportunitiesMock.mockReturnValue(new Promise(() => {}))
    render(<MarketsWorkspace />)
    expect(screen.getByRole('status', { busy: true })).toBeTruthy()
    expect(screen.getByText('正在加载市场数据')).toBeTruthy()
  })

  it('keeps an honest typed error with retry on list-level failure', async () => {
    listMarketOpportunitiesMock.mockRejectedValue(await apiError(429, 'rate_limited'))
    const user = userEvent.setup()
    render(<MarketsWorkspace />)

    await waitFor(() => expect(screen.getByText(/rate_limited/)).toBeTruthy())
    expect(screen.getByRole('alert')).toBeTruthy()

    listMarketOpportunitiesMock.mockResolvedValue({
      rows: [opportunityDto()],
      availability: { reason: 'HAS_OPPORTUNITIES', model_status: 'unknown' },
    })
    await user.click(screen.getByRole('button', { name: /重试加载/ }))
    await waitFor(() => expect(screen.getByText('Alpha One vs. Beta Two')).toBeTruthy())
  })

  it('keeps last trusted rows visible when a refresh fails', async () => {
    const user = userEvent.setup()
    listMarketsMock.mockResolvedValue({
      markets: [summaryDto({ is_stale: true, decision_action: 'wait' })],
      page: 1,
      page_size: 50,
      total: 1,
    })
    render(<MarketsWorkspace />)
    await user.click(screen.getByRole('tab', { name: /全部市场/ }))
    await waitFor(() => expect(screen.getByText(/部分市场已超过 freshness 阈值/)).toBeTruthy())
    expect(screen.getAllByText(/最后可信 ·/).length).toBeGreaterThanOrEqual(1)
    // The stale row shows the revoked-action badge, never a fresh BUY.
    expect(screen.getByText('WAIT')).toBeTruthy()
    expect(screen.queryByText('BUY')).toBeNull()
  })

  it('renders closed markets with the closed phase badge', async () => {
    listMarketsMock.mockResolvedValue({
      markets: [summaryDto({ phase: 'closed', status: 'closed', decision_action: 'no_bet' })],
      page: 1,
      page_size: 50,
      total: 1,
    })
    const user = userEvent.setup()
    render(<MarketsWorkspace />)
    await user.click(screen.getByRole('tab', { name: /全部市场/ }))
    // The closed badge appears on the row (plus the phase filter chip).
    await waitFor(() => expect(screen.getAllByText('已收盘').length).toBeGreaterThanOrEqual(2))
    expect(screen.getByText('NO BET')).toBeTruthy()
  })

  it('renders honest empty states per view', async () => {
    listMarketOpportunitiesMock.mockResolvedValue({
      rows: [],
      availability: { reason: 'NO_ELIGIBLE_ACTION', model_status: 'unknown' },
    })
    listMarketsMock.mockResolvedValue({ markets: [], page: 1, page_size: 50, total: 0 })
    getPaperPositionsMock.mockResolvedValue({ open: [], recent: [] })
    const user = userEvent.setup()
    render(<MarketsWorkspace />)

    // NO_ELIGIBLE_ACTION has its own honest copy (T88).
    await waitFor(() => expect(screen.getByText('当前没有满足策略门的机会。')).toBeTruthy())
    await user.click(screen.getByRole('tab', { name: /全部市场/ }))
    await waitFor(() => expect(screen.getByText('供应商暂无市场')).toBeTruthy())
    await user.click(screen.getByRole('button', { name: 'ITF' }))
    await waitFor(() => expect(screen.getByText('筛选后无市场')).toBeTruthy())
    await user.click(screen.getByRole('tab', { name: /^Paper/ }))
    await waitFor(() => expect(screen.getByText('暂无 Paper 记录')).toBeTruthy())
  })

  it('renders the honest disabled panel on p3_disabled', async () => {
    const error = await apiError(503, 'p3_disabled')
    listMarketOpportunitiesMock.mockRejectedValue(error)
    listMarketsMock.mockRejectedValue(error)
    getPaperPositionsMock.mockRejectedValue(error)
    render(<MarketsWorkspace />)

    await waitFor(() => expect(screen.getByText('市场决策支持未启用')).toBeTruthy())
    expect(screen.getByText(/p3_disabled/)).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
// T88: the empty opportunities tab explains itself with server-provided
// availability reasons; a low-tier row never carries a negative model label.
// ---------------------------------------------------------------------------

describe('MarketsWorkspace opportunity empty states (T88)', () => {
  // This describe sits outside the production describe, so it must reset the
  // shared mocks itself instead of inheriting the previous test's failures.
  beforeEach(() => {
    listMarketsMock.mockResolvedValue({
      markets: [],
      page: 1,
      page_size: 50,
      total: 0,
    })
    getPaperPositionsMock.mockResolvedValue({ open: [], recent: [] })
  })

  function emptyOpportunities(reason: OpportunityAvailabilityReason | null) {
    listMarketOpportunitiesMock.mockResolvedValue({
      rows: [],
      availability: reason === null ? null : { reason, model_status: 'unknown' },
    })
  }

  it('explains an unpromoted model and offers the real quotes', async () => {
    emptyOpportunities('ELIGIBLE_UNPROMOTED')
    render(<MarketsWorkspace initialView="opportunities" />)

    await waitFor(() =>
      expect(screen.getByText('模型尚未完成验证')).toBeTruthy(),
    )
    expect(
      screen.getByText('模型尚未完成验证，当前不生成 BUY / WAIT；全部市场的真实报价仍可查看。'),
    ).toBeTruthy()
    expect(screen.getByRole('button', { name: '查看全部市场' })).toBeTruthy()
    expect(screen.queryByText('BUY')).toBeNull()
    expect(screen.queryByText('WAIT')).toBeNull()
  })

  it('uses a distinct honest copy for every other reason', async () => {
    const cases = [
      ['NO_ELIGIBLE_ACTION', '当前没有满足策略门的机会。'],
      ['NO_COVERED_MARKET', '当前没有可评估的主巡单打市场。'],
      ['DECISION_GAP', '决策数据正在恢复，暂不生成新机会。'],
    ] as const
    for (const [reason, copy] of cases) {
      emptyOpportunities(reason)
      const { unmount } = render(<MarketsWorkspace initialView="opportunities" />)
      await waitFor(() => expect(screen.getByText(copy)).toBeTruthy())
      unmount()
    }
  })

  it('falls back to the neutral copy when the payload carries no reason', async () => {
    emptyOpportunities(null)
    render(<MarketsWorkspace initialView="opportunities" />)

    await waitFor(() => expect(screen.getByText('暂无符合门槛的机会')).toBeTruthy())
    expect(screen.queryByRole('button', { name: '查看全部市场' })).toBeNull()
  })

  it('switching to the all-markets view works from the empty state', async () => {
    const user = userEvent.setup()
    emptyOpportunities('ELIGIBLE_UNPROMOTED')
    render(<MarketsWorkspace initialView="opportunities" />)

    await waitFor(() => expect(screen.getByText('模型尚未完成验证')).toBeTruthy())
    await user.click(screen.getByRole('button', { name: '查看全部市场' }))
    await waitFor(() => expect(screen.getByText('市场筛选')).toBeTruthy())
  })
})
