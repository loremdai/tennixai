import { act, cleanup, render, screen } from '@testing-library/react'
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
    expect(tabs.map((tab) => tab.textContent)).toEqual([
      '机会模型判断与关注理由',
      '全部市场比赛与最新报价',
      '模拟记录仅供模拟，不涉及真实资金',
    ])
    expect(screen.getByRole('tabpanel')).toHaveAttribute('id', 'markets-panel-opportunities')

    await user.click(screen.getByRole('tab', { name: /全部市场/ }))
    expect(screen.getByRole('tabpanel')).toHaveAttribute('id', 'markets-panel-all')
    expect(screen.getByText('市场筛选')).toBeVisible()

    await user.click(screen.getByRole('tab', { name: /^模拟记录/ }))
    expect(screen.getByRole('tabpanel')).toHaveAttribute('id', 'markets-panel-paper')
    expect(screen.getByRole('heading', { name: '模拟记录' })).toBeVisible()
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

  it('uses customer language for preview states instead of implementation labels', () => {
    render(
      <MarketsPage
        initialView="opportunities"
        initialState="populated"
        initialTiers={[]}
        initialGender="all"
        initialPhase="all"
      />,
    )

    expect(screen.getByRole('heading', { name: '比赛市场' })).toBeVisible()
    expect(document.body.textContent).toContain('有买入或观望信号')
    expect(document.body.textContent).not.toMatch(/BUY \+ WAIT|部分 stale|Markets · P3/)
  })

  it('labels preview exits as reference estimates rather than guaranteed proceeds', () => {
    render(
      <MarketsPage
        initialView="paper"
        initialState="populated"
        initialTiers={[]}
        initialGender="all"
        initialPhase="all"
      />,
    )

    expect(screen.getAllByText('退出参考金额').length).toBeGreaterThan(0)
    expect(
      screen.getAllByText('按当前最高买价估算，未扣费用，也不保证全部份额都能按此价格卖出。').length,
    ).toBeGreaterThan(0)
  })

  it('distinguishes planned quotes from held positions in preview records', () => {
    render(
      <MarketsPage
        initialView="paper"
        initialState="populated"
        initialTiers={[]}
        initialGender="all"
        initialPhase="all"
      />,
    )

    const pending = screen.getByRole('link', {
      name: '查看 Aryna Sabalenka vs Coco Gauff 的模拟记录',
    })
    expect(pending.textContent).toContain('计划投入 / 报价均价')
    expect(pending.textContent).toContain('预计份额')
    expect(pending.textContent).not.toContain('持有份额')
  })

  it('does not present a missed preview entry as money spent or shares held', () => {
    render(
      <MarketsPage
        initialView="paper"
        initialState="terminal"
        initialTiers={[]}
        initialGender="all"
        initialPhase="all"
      />,
    )

    const missed = screen.getByRole('link', {
      name: '查看 Qinwen Zheng vs Elena Rybakina 的模拟记录',
    })
    expect(missed.textContent).toContain('— · —')
    expect(missed.textContent).not.toContain('$10.00 · 54.0%')
    expect(missed.textContent).not.toContain('0.00')
  })

  it('describes the quote spread and best-level amount without implying full depth', async () => {
    render(
      <MarketsPage
        initialView="all"
        initialState="populated"
        initialTiers={[]}
        initialGender="all"
        initialPhase="all"
      />,
    )

    expect(await screen.findByRole('heading', { name: '比赛市场' })).toBeVisible()
    const spreadLabels = screen.getAllByText('平均价差')
    const depthLabels = screen.getAllByText('最优档金额')
    expect(spreadLabels.length).toBeGreaterThan(0)
    expect(depthLabels.length).toBeGreaterThan(0)
    expect(spreadLabels[0]).toHaveAttribute('title', '每位球员都同时有买入价和卖出价时，才计入平均值。')
    expect(depthLabels[0]).toHaveAttribute('title', '双方买卖盘最优一档的金额合计，不代表整个盘口，也不保证全部可成交。')
    expect(document.body.textContent).not.toMatch(/\bspread\b|\bdepth\b|主巡覆盖|不伪造模型值/)
    expect(screen.getAllByText('暂不提供胜率估算').length).toBeGreaterThan(0)
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
  useMarketStreamMock,
} = vi.hoisted(() => ({
  listMarketOpportunitiesMock: vi.fn(),
  listMarketsMock: vi.fn(),
  getPaperPositionsMock: vi.fn(),
  useMarketStreamMock: vi.fn(),
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
  useMarketStream: useMarketStreamMock,
}))

let onQuotesChanged: ((event: { sequence: number; count: number; as_of: string }) => void) | undefined
const STATIC_MARKET_STREAM_STATE = {
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
}

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
    onQuotesChanged = undefined
    useMarketStreamMock.mockImplementation((options: {
      onQuotesChanged?: typeof onQuotesChanged
    }) => {
      onQuotesChanged = options.onQuotesChanged
      return STATIC_MARKET_STREAM_STATE
    })
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
    const rows = screen.getAllByRole('link', { name: /查看 .* 的(模拟买入机会|等待更好价格)决策/ })
    expect(rows.map((row) => row.getAttribute('href'))).toEqual([
      '/matches/mat_1',
      '/matches/mat_2',
    ])
    expect(screen.getByText('方向：Beta Two')).toBeTruthy()
    expect(screen.getByText('方向：Gamma Three')).toBeTruthy()
    expect(screen.getByText('模拟买入机会')).toBeTruthy()
    expect(screen.getByText('等待更好价格')).toBeTruthy()
    expect(screen.getByText('+7.0 个百分点')).toBeTruthy()
    expect(screen.getByText('最高买入价 55.0%')).toBeTruthy()
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
    await user.click(screen.getByRole('tab', { name: /模拟记录/ }))
    expect(
      screen.queryAllByRole('button', { name: /BUY|SELL|钱包|下单|真实交易/ }),
    ).toHaveLength(0)
  })

  it('identifies which player the market-row model probability belongs to', async () => {
    const user = userEvent.setup()
    render(<MarketsWorkspace />)
    await user.click(screen.getByRole('tab', { name: /全部市场/ }))

    await waitFor(() => expect(screen.getByText('Alpha One 模型胜率')).toBeTruthy())
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

  it('shows the full server total, loads more, and quote changes refresh only loaded pages', async () => {
    const firstPage = Array.from({ length: 50 }, (_, index) =>
      summaryDto({
        market_id: `mkt_${index}`,
        tier: 'atp',
        gender: 'men',
        player_names: [`Player ${index}`, `Opponent ${index}`],
      }),
    )
    const tailRow = summaryDto({
      market_id: 'mkt_50',
      tier: 'wta',
      gender: 'women',
      player_names: ['Player Tail', 'Opponent Tail'],
    })
    listMarketsMock.mockImplementation(async ({ page }: { page: number }) =>
      page === 1
        ? { markets: firstPage, page: 1, page_size: 50, total: 51 }
        : { markets: [tailRow], page: 2, page_size: 50, total: 51 },
    )
    const user = userEvent.setup()
    render(<MarketsWorkspace initialView="all" />)

    await waitFor(() => expect(screen.getByText('已加载 50 / 51 场')).toBeTruthy())
    await user.click(screen.getByRole('button', { name: '女子' }))
    expect(screen.getByText('没有符合条件的比赛')).toBeTruthy()
    expect(screen.getByRole('button', { name: '加载更多' })).toBeTruthy()
    await user.click(screen.getByRole('button', { name: '加载更多' }))
    await waitFor(() =>
      expect(screen.getByRole('link', { name: '查看 Player Tail vs. Opponent Tail 市场' })).toBeTruthy(),
    )
    expect(screen.getByText('已加载 51 / 51 场')).toBeTruthy()

    const opportunityCalls = listMarketOpportunitiesMock.mock.calls.length
    const paperCalls = getPaperPositionsMock.mock.calls.length
    const marketCalls = listMarketsMock.mock.calls.length
    await act(async () => {
      onQuotesChanged?.({ sequence: 5, count: 2, as_of: AS_OF })
      onQuotesChanged?.({ sequence: 6, count: 2, as_of: AS_OF })
      onQuotesChanged?.({ sequence: 7, count: 1, as_of: AS_OF })
    })
    await waitFor(() =>
      expect(listMarketsMock).toHaveBeenCalledTimes(marketCalls + 2),
    )
    expect(listMarketsMock.mock.calls.slice(-2)).toEqual([
      [{ page: 1, pageSize: 50 }],
      [{ page: 2, pageSize: 50 }],
    ])
    expect(listMarketOpportunitiesMock).toHaveBeenCalledTimes(opportunityCalls)
    expect(getPaperPositionsMock).toHaveBeenCalledTimes(paperCalls)
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
    await user.click(screen.getByRole('tab', { name: /^模拟记录/ }))

    await waitFor(() => expect(screen.getByRole('heading', { name: '模拟记录' })).toBeTruthy())
    expect(screen.getByText('3 条')).toBeTruthy()
    const badges = screen.getAllByText(/^(模拟持有中|等待买入确认|已结算)$/)
    expect(badges.map((badge) => badge.textContent)).toEqual([
      '模拟持有中',
      '等待买入确认',
      '已结算',
    ])
    expect(screen.getAllByText('$10.00 · 52.5%')).toHaveLength(3)
    expect(screen.getByText('+$1.40')).toBeTruthy()
    expect(screen.getAllByText('退出参考金额').length).toBeGreaterThan(0)
    expect(
      screen.getAllByText('按当前最高买价估算，未扣费用，也不保证全部份额都能按此价格卖出。').length,
    ).toBeGreaterThan(0)
    expect(screen.getByText(/不会触发真实交易/)).toBeTruthy()
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

    await waitFor(() => expect(screen.getByText('请求过于频繁，请稍后再试。')).toBeTruthy())
    expect(screen.queryByText(/rate_limited/)).toBeNull()
    expect(screen.getByRole('alert')).toBeTruthy()

    listMarketOpportunitiesMock.mockResolvedValue({
      rows: [opportunityDto()],
      availability: { reason: 'HAS_OPPORTUNITIES', model_status: 'unknown' },
    })
    await user.click(screen.getByRole('button', { name: /重试加载/ }))
    await waitFor(() => expect(screen.getByText('Alpha One vs. Beta Two')).toBeTruthy())
  })

  it('keeps stale decision rows visible without marking a fresh quote stale', async () => {
    const user = userEvent.setup()
    listMarketsMock.mockResolvedValue({
      markets: [summaryDto({ is_stale: true, decision_action: 'wait' })],
      page: 1,
      page_size: 50,
      total: 1,
    })
    render(<MarketsWorkspace />)
    await user.click(screen.getByRole('tab', { name: /全部市场/ }))
    await waitFor(() => expect(screen.getAllByText(/报价更新较慢/).length).toBeGreaterThan(0))
    expect(screen.queryByText(/最后可信 ·/)).toBeNull()
    // The decision is stale and its action is revoked; the quote timestamp is independent.
    expect(screen.getByText('等待更好价格')).toBeTruthy()
    expect(screen.queryByText('买入信号')).toBeNull()
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
    await waitFor(() => expect(screen.getAllByText('已结束').length).toBeGreaterThanOrEqual(2))
    expect(screen.getByText('暂不参与')).toBeTruthy()
  })

  it('labels markets with missing phase as unknown instead of completed', async () => {
    listMarketsMock.mockResolvedValue({
      markets: [summaryDto({ phase: null, status: 'unknown' })],
      page: 1,
      page_size: 50,
      total: 1,
    })
    const user = userEvent.setup()
    render(<MarketsWorkspace />)
    await user.click(screen.getByRole('tab', { name: /全部市场/ }))

    expect(await screen.findByText('状态未知')).toBeTruthy()
    // Only the phase filter uses this label; the market row must not claim it ended.
    expect(screen.getAllByText('已结束')).toHaveLength(1)
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
    await waitFor(() => expect(screen.getByText('目前没有符合条件的比赛。')).toBeTruthy())
    await user.click(screen.getByRole('tab', { name: /全部市场/ }))
    await waitFor(() => expect(screen.getByText('目前没有可显示的比赛报价')).toBeTruthy())
    await user.click(screen.getByRole('button', { name: 'ITF 巡回赛' }))
    await waitFor(() => expect(screen.getByText('没有符合条件的比赛')).toBeTruthy())
    await user.click(screen.getByRole('tab', { name: /^模拟记录/ }))
    await waitFor(() => expect(screen.getByText('暂无模拟记录')).toBeTruthy())
  })

  it('renders the honest disabled panel on p3_disabled', async () => {
    const error = await apiError(503, 'p3_disabled')
    listMarketOpportunitiesMock.mockRejectedValue(error)
    listMarketsMock.mockRejectedValue(error)
    getPaperPositionsMock.mockRejectedValue(error)
    render(<MarketsWorkspace />)

    await waitFor(() => expect(screen.getByText('市场功能暂不可用')).toBeTruthy())
    expect(screen.getByText('市场功能暂未开放；比赛和球员信息仍可正常使用。')).toBeTruthy()
    expect(screen.queryByText(/p3_disabled/)).toBeNull()
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
      expect(screen.getByText('模型仍在验证中')).toBeTruthy(),
    )
    expect(
      screen.getByText('模型验证尚未完成，因此暂不提供比赛判断；你仍可查看所有市场的最新报价。'),
    ).toBeTruthy()
    expect(screen.getByRole('button', { name: '查看所有比赛报价' })).toBeTruthy()
    expect(screen.queryByText('买入信号')).toBeNull()
    expect(screen.queryByText('等待更好价格')).toBeNull()
  })

  it('uses a distinct honest copy for every other reason', async () => {
    const cases = [
      ['NO_ELIGIBLE_ACTION', '目前没有符合条件的比赛。'],
      ['NO_COVERED_MARKET', '目前没有纳入分析的单打比赛；其他比赛的市场报价仍可查看。'],
      ['DECISION_GAP', '我们已暂停提供新的比赛判断，请稍后再试。'],
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

    await waitFor(() => expect(screen.getByText('暂时没有可关注的机会')).toBeTruthy())
    expect(screen.getByRole('button', { name: '查看所有比赛报价' })).toBeTruthy()
  })

  it('switching to the all-markets view works from the empty state', async () => {
    const user = userEvent.setup()
    emptyOpportunities('ELIGIBLE_UNPROMOTED')
    render(<MarketsWorkspace initialView="opportunities" />)

    await waitFor(() => expect(screen.getByText('模型仍在验证中')).toBeTruthy())
    await user.click(screen.getByRole('button', { name: '查看所有比赛报价' }))
    await waitFor(() => expect(screen.getByText('市场筛选')).toBeTruthy())
  })
})
