import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { HomePage } from './home-page'
import type {
  ChatEvent,
  FacetCountsDto,
  MatchCatalogDto,
  MatchDto,
  MatchFiltersDto,
  PlayerHistoryContextDto,
  StructuredData,
} from '@/lib/api/types'
import { DEFAULT_MATCH_FILTERS } from '@/lib/match-filters'

const {
  getMatchCatalogMock,
  getMatchesMock,
  getPlayersMock,
  getMatchMock,
  streamChatMock,
  getMarketPulseMock,
  openMarketStreamMock,
} = vi.hoisted(() => ({
  getMatchCatalogMock: vi.fn(),
  getMatchesMock: vi.fn(),
  getPlayersMock: vi.fn(),
  getMatchMock: vi.fn(),
  streamChatMock: vi.fn(),
  getMarketPulseMock: vi.fn(),
  openMarketStreamMock: vi.fn(),
}))

vi.mock('@/lib/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api/client')>()
  return {
    ...actual,
    getMatchCatalog: getMatchCatalogMock,
    getMatches: getMatchesMock,
    getPlayers: getPlayersMock,
    getMatch: getMatchMock,
    streamChat: streamChatMock,
    getMarketPulse: getMarketPulseMock,
    openMarketStream: openMarketStreamMock,
  }
})

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams(),
}))

const liveDto: MatchDto = {
  id: 'mat_live1',
  status: 'live',
  players: [
    { id: 'ply_1', name: 'Jannik Sinner', country_code: 'ita', ranking: 1 },
    { id: 'ply_3', name: 'Casper Ruud', country_code: 'nor', ranking: 4 },
  ],
  tournament: { id: 'trn_1', name: 'ATP Finals', tour: 'atp' },
  scheduled_at: '2026-09-08T10:00:00Z',
  round: 'Semifinal',
  surface: 'hard',
  indoor: true,
  format: 'BO3',
  live_state: {
    score: {
      sets_won: [1, 1],
      sets: [
        { number: 1, player1_games: 6, player2_games: 4 },
        { number: 2, player1_games: 4, player2_games: 6 },
        { number: 3, player1_games: 4, player2_games: 5 },
      ],
      points: ['30', '15'],
      is_tiebreak: false,
    },
    server_player_id: 'ply_1',
  },
  winner_player_id: null,
  freshness: {
    provider: 'fake',
    source_updated_at: null,
    observed_at: '2026-09-08T10:00:00Z',
    is_stale: false,
    age_seconds: 0,
  },
}

const upcomingDto: MatchDto = {
  id: 'mat_up1',
  status: 'scheduled',
  players: [
    { id: 'ply_1', name: 'Jannik Sinner', country_code: 'ita', ranking: 1 },
    { id: 'ply_2', name: 'Carlos Alcaraz', country_code: 'esp', ranking: 2 },
  ],
  tournament: { id: 'trn_1', name: 'ATP Finals', tour: 'atp' },
  scheduled_at: '2026-09-08T12:30:00Z',
  round: 'Semifinal',
  surface: 'hard',
  indoor: true,
  format: 'BO3',
  live_state: null,
  winner_player_id: null,
  freshness: {
    provider: 'fake',
    source_updated_at: null,
    observed_at: '2026-09-08T10:00:00Z',
    is_stale: false,
    age_seconds: 0,
  },
}

const emptyFacetCounts: FacetCountsDto = {
  circuits: { atp: 0, wta: 0, challenger: 0, itf: 0, other: 0 },
  genders: { men: 0, women: 0, mixed: 0, unknown: 0 },
  disciplines: { singles: 0, doubles: 0, team: 0, unknown: 0 },
}

// ------------------------------------------------------------- T54 history DTOs

const finishedHistoryDto: MatchDto = {
  id: 'mat_hist_1',
  status: 'finished',
  players: [
    { id: 'ply_s', name: 'Jannik Sinner', country_code: 'ita', ranking: 1, localized_name: '辛纳' },
    { id: 'ply_o', name: 'Opponent One', country_code: 'fra', ranking: 40 },
  ],
  tournament: { id: 'trn_h', name: 'US Open', tour: 'atp' },
  scheduled_at: '2026-08-20T10:00:00Z',
  round: 'Quarterfinal',
  surface: 'hard',
  indoor: false,
  format: 'BO5',
  live_state: null,
  winner_player_id: 'ply_s',
  freshness: {
    provider: 'fake',
    source_updated_at: null,
    observed_at: '2026-08-20T12:00:00Z',
    is_stale: false,
    age_seconds: 0,
  },
}

function playerHistoryData(
  history: Partial<PlayerHistoryContextDto> & Pick<PlayerHistoryContextDto, 'player' | 'scope'>,
  matches: MatchDto[] = [],
): StructuredData {
  return {
    kind: 'player_history',
    matches,
    player_history: {
      season: null,
      availability: 'available',
      season_record: null,
      empty_reason: null,
      ...history,
    },
  }
}

const sinnerPlayer = {
  id: 'ply_s',
  name: 'Jannik Sinner',
  country_code: 'ita',
  ranking: 1,
  localized_name: '辛纳',
}
const zhengPlayer = {
  id: 'ply_z',
  name: 'Qinwen Zheng',
  country_code: 'chn',
  ranking: 5,
  localized_name: '郑钦文',
}

function makeCatalog(
  status: 'live' | 'upcoming',
  matches: MatchDto[],
  overrides: Partial<MatchCatalogDto> = {},
): MatchCatalogDto {
  // Non-zero counts everywhere so facet chips stay clickable in tests;
  // disabled-state behavior is covered in match-filters.test.tsx.
  const count = Math.max(matches.length, 1)
  return {
    status,
    matches,
    filters: {
      circuits: [...DEFAULT_MATCH_FILTERS.circuits],
      genders: [...DEFAULT_MATCH_FILTERS.genders],
      disciplines: [...DEFAULT_MATCH_FILTERS.disciplines],
    },
    facet_counts: {
      circuits: { atp: count, wta: count, challenger: count, itf: count, other: count },
      genders: { men: count, women: count, mixed: count, unknown: count },
      disciplines: { singles: count, doubles: count, team: count, unknown: count },
    },
    featured_match_id: matches[0]?.id ?? null,
    ...overrides,
  }
}

function mockStream(options: {
  data?: StructuredData
  dataItems?: StructuredData[]
  text?: string
  errorCode?: string
  errorDetails?: Record<string, unknown>
  warningMessage?: string
}) {
  streamChatMock.mockImplementation(() => {
    async function* generate(): AsyncGenerator<ChatEvent> {
      yield { type: 'status', payload: { stage: 'resolving' } }
      const payloads = options.dataItems ?? (options.data ? [options.data] : [])
      for (const payload of payloads) {
        yield { type: 'data', payload }
      }
      if (options.text) yield { type: 'text_delta', payload: { delta: options.text } }
      if (options.warningMessage) {
        yield {
          type: 'warning',
          payload: { code: 'optional_data_unavailable', message: options.warningMessage, details: {} },
        }
      }
      if (options.errorCode) {
        yield {
          type: 'error',
          payload: { code: options.errorCode, message: 'failed', details: options.errorDetails ?? {} },
        }
      } else {
        yield { type: 'done', payload: { ok: true } }
      }
    }
    return generate()
  })
}

beforeEach(async () => {
  vi.clearAllMocks()
  Element.prototype.scrollIntoView = vi.fn()
  getMatchCatalogMock.mockImplementation(async (status: 'live' | 'upcoming') =>
    makeCatalog(status, status === 'live' ? [liveDto] : [upcomingDto]),
  )
  mockStream({ data: { kind: 'matches', matches: [upcomingDto] }, text: 'Sinner 今晚 20:30 出场。' })
  // Default: P3 disabled backend — the production Home visuals must match
  // the pre-P3 baselines exactly (placeholder card, no pulse section).
  const { ApiError } = await import('@/lib/api/client')
  getMarketPulseMock.mockRejectedValue(new ApiError(503, 'p3_disabled', 'disabled'))
  openMarketStreamMock.mockImplementation(() =>
    Promise.resolve(
      new Response(new ReadableStream({ start() {} }), {
        status: 200,
        headers: { 'content-type': 'text/event-stream' },
      }),
    ),
  )
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

async function askQuestion(question: string) {
  const input = screen.getByLabelText('继续向 Tennix 提问')
  await userEvent.type(input, question)
  await userEvent.keyboard('{Enter}')
}

describe('HomePage slate', () => {
  it('loads live and upcoming catalogs exactly once without polling timers', async () => {
    render(<HomePage />)

    await screen.findByText('Jannik Sinner')
    await waitFor(() => {
      expect(getMatchCatalogMock).toHaveBeenCalledWith('live', DEFAULT_MATCH_FILTERS)
      expect(getMatchCatalogMock).toHaveBeenCalledWith('upcoming', DEFAULT_MATCH_FILTERS)
    })
    expect(getMatchCatalogMock).toHaveBeenCalledTimes(2)

    // No polling: the call count stays stable over time without user action.
    await new Promise((resolve) => setTimeout(resolve, 150))
    expect(getMatchCatalogMock).toHaveBeenCalledTimes(2)
  })

  it('refresh makes exactly one new pair of calls', async () => {
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    await userEvent.click(screen.getByRole('button', { name: '刷新比赛数据' }))

    await waitFor(() => {
      expect(getMatchCatalogMock).toHaveBeenCalledTimes(4)
    })
  })

  it('keeps section shells with factual empty copy when lists are empty', async () => {
    getMatchCatalogMock.mockImplementation(async (status: 'live' | 'upcoming') =>
      makeCatalog(status, [], { facet_counts: emptyFacetCounts }),
    )

    render(<HomePage />)

    expect(await screen.findByText('暂无直播比赛')).toBeVisible()
    expect(screen.getByText('今晚暂无待开赛比赛')).toBeVisible()
    expect(screen.getByRole('heading', { name: '正在直播' })).toBeVisible()
    expect(screen.getByRole('heading', { name: '今晚比赛' })).toBeVisible()
  })

  it('shows flags on Home match cards without adding country names', async () => {
    render(<HomePage />)

    await screen.findByText('Jannik Sinner')
    expect(screen.getAllByRole('img', { name: '意大利国旗' }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('img', { name: '西班牙国旗' }).length).toBeGreaterThan(0)
    expect(screen.queryByText('意大利')).toBeNull()
  })

  it('renders typed retry copy when the slate API fails', async () => {
    getMatchCatalogMock.mockRejectedValue(Object.assign(new Error('down'), { code: 'provider_unavailable' }))

    render(<HomePage />)

    expect(await screen.findByText(/provider_unavailable/)).toBeVisible()
    const retry = screen.getByRole('button', { name: '重试加载比赛数据' })
    expect(retry).toBeVisible()
  })

  it('keeps the healthy upcoming section when live loading fails', async () => {
    getMatchCatalogMock.mockImplementation(async (status: 'live' | 'upcoming') => {
      if (status === 'live') {
        throw Object.assign(new Error('live down'), { code: 'provider_unavailable' })
      }
      return makeCatalog(status, [upcomingDto])
    })

    render(<HomePage />)

    expect(await screen.findByText(/直播比赛加载失败（provider_unavailable）/)).toBeVisible()
    expect(screen.getByRole('heading', { name: '今晚比赛' })).toBeVisible()
    expect(screen.getByText('Carlos Alcaraz')).toBeVisible()
    expect(screen.queryByText(/比赛数据加载失败（provider_unavailable）/)).toBeNull()
  })

  it('offers all provider live matches when the approved default facets hide them', async () => {
    getMatchCatalogMock.mockImplementation(async (
      status: 'live' | 'upcoming',
      requestedFilters: MatchFiltersDto = DEFAULT_MATCH_FILTERS,
    ) => {
      if (status === 'live' && requestedFilters.circuits.length === 0) {
        return makeCatalog(status, [liveDto], { facet_counts: emptyFacetCounts })
      }
      if (status === 'live') {
        return makeCatalog(status, [], {
          facet_counts: {
            ...emptyFacetCounts,
            circuits: { ...emptyFacetCounts.circuits, itf: 1 },
          },
        })
      }
      return makeCatalog(status, [upcomingDto])
    })

    render(<HomePage />)

    expect(await screen.findByText('当前筛选暂无直播，其他赛事发现可用直播')).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: '显示全部直播' }))

    await waitFor(() => {
      expect(getMatchCatalogMock).toHaveBeenCalledWith('live', {
        circuits: [],
        genders: [],
        disciplines: [],
      })
    })
    expect(await screen.findByText('Jannik Sinner')).toBeVisible()
  })
})

describe('HomePage P3 preview', () => {
  it('replaces the legacy Market Intelligence card with one market pulse section', async () => {
    render(<HomePage previewP3 initialPulseState="populated" />)

    expect(await screen.findByRole('heading', { name: '市场脉搏' })).toBeVisible()
    expect(screen.queryByRole('heading', { name: 'Market Intelligence' })).toBeNull()
  })
})

describe('HomePage production P3', () => {
  it('keeps the placeholder card and anchor link when P3 is disabled', async () => {
    render(<HomePage />)

    expect(await screen.findByRole('heading', { name: 'Market Intelligence' })).toBeVisible()
    expect(screen.queryByRole('heading', { name: '市场脉搏' })).toBeNull()
    expect(screen.getByRole('link', { name: /市场/ })).toHaveAttribute('href', '/#markets')
    // A disabled deployment makes zero P3 requests from the browser.
    expect(getMarketPulseMock).not.toHaveBeenCalled()
  })

  it('replaces the placeholder with the live pulse when P3 is enabled', async () => {
    getMarketPulseMock.mockResolvedValue({
      data: [
        {
          match_id: 'mat_live1',
          market_id: 'mkt_1',
          kind: 'opportunity',
          action: 'buy',
          phase: 'live',
          player_names: ['Jannik Sinner', 'Casper Ruud'],
          model_probability: 0.62,
          executable_probability: 0.55,
          conservative_net_edge: '0.0700',
          tournament_name: 'ATP Finals',
          is_stale: false,
          has_gap: false,
          as_of: new Date().toISOString(),
        },
      ],
      has_open_position: false,
    })
    render(<HomePage p3Enabled />)

    expect(await screen.findByRole('heading', { name: '市场脉搏' })).toBeVisible()
    expect(screen.queryByRole('heading', { name: 'Market Intelligence' })).toBeNull()
    expect(screen.getByRole('link', { name: /市场/ })).toHaveAttribute('href', '/markets')
    expect(
      screen.getByRole('link', { name: /查看 Jannik Sinner vs\. Casper Ruud 的 buy 决策/ }),
    ).toHaveAttribute('href', '/matches/mat_live1')
  })
})

describe('HomePage facets', () => {
  it('shows the filter groups with default active facets', async () => {
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    expect(screen.getByRole('group', { name: '赛事级别' })).toBeVisible()
    expect(screen.getByRole('button', { name: /ATP/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /WTA/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /单打/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /Challenger/ })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.queryByRole('button', { name: '恢复默认' })).toBeNull()
  })

  it('follows featured_match_id instead of the first array item', async () => {
    const secondLive: MatchDto = {
      ...liveDto,
      id: 'mat_live2',
      players: [
        { id: 'ply_5', name: 'Iga Swiatek', country_code: 'pol', ranking: 1 },
        { id: 'ply_6', name: 'Aryna Sabalenka', country_code: 'blr', ranking: 2 },
      ],
      tournament: { id: 'trn_2', name: 'WTA Finals', tour: 'wta', circuit: 'wta', gender: 'women', discipline: 'singles' },
    }
    getMatchCatalogMock.mockImplementation(async (status: 'live' | 'upcoming') =>
      status === 'live'
        ? makeCatalog(status, [liveDto, secondLive], { featured_match_id: 'mat_live2' })
        : makeCatalog(status, [upcomingDto]),
    )

    render(<HomePage />)
    await screen.findByText('Iga Swiatek')

    const featuredLink = screen.getByRole('link', { name: '打开比赛' })
    expect(featuredLink).toHaveAttribute('href', '/matches/mat_live2')
  })

  it('refetches both sections with stacked filters and never relaxes them', async () => {
    getMatchCatalogMock.mockImplementation(async (status: 'live' | 'upcoming') => {
      const call = getMatchCatalogMock.mock.calls.at(-1)?.[1] ?? DEFAULT_MATCH_FILTERS
      if (call.genders.includes('women')) {
        return makeCatalog(status, [], { facet_counts: emptyFacetCounts })
      }
      return makeCatalog(status, status === 'live' ? [liveDto] : [upcomingDto])
    })

    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    await userEvent.click(screen.getByRole('button', { name: /女子/ }))

    await waitFor(() => {
      expect(getMatchCatalogMock).toHaveBeenCalledWith('live', {
        circuits: ['atp', 'wta'],
        genders: ['women'],
        disciplines: ['singles'],
      })
      expect(getMatchCatalogMock).toHaveBeenCalledWith('upcoming', {
        circuits: ['atp', 'wta'],
        genders: ['women'],
        disciplines: ['singles'],
      })
    })
    // Filtered-empty shows the empty state; the filters stay exactly as chosen.
    expect(await screen.findByText('暂无直播比赛')).toBeVisible()
    expect(screen.getByRole('button', { name: /女子/ })).toHaveAttribute('aria-pressed', 'true')
    const lastFilters = getMatchCatalogMock.mock.calls.at(-1)?.[1]
    expect(lastFilters).toEqual({
      circuits: ['atp', 'wta'],
      genders: ['women'],
      disciplines: ['singles'],
    })
  })

  it('restores the approved defaults with 恢复默认', async () => {
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    await userEvent.click(screen.getByRole('button', { name: /女子/ }))
    const reset = await screen.findByRole('button', { name: '恢复默认' })
    await userEvent.click(reset)

    await waitFor(() => {
      const lastFilters = getMatchCatalogMock.mock.calls.at(-1)?.[1]
      expect(lastFilters).toEqual(DEFAULT_MATCH_FILTERS)
    })
    expect(screen.queryByRole('button', { name: '恢复默认' })).toBeNull()
    expect(screen.getByRole('button', { name: /女子/ })).toHaveAttribute('aria-pressed', 'false')
  })
})

describe('HomePage chat', () => {
  it('keeps internal prompt and implementation labels out of the Home answer card', async () => {
    mockStream({
      data: { kind: 'intelligence', matches: [] },
      text: '本场比赛分析已完成。',
    })
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    const question = '根据本场数据分析趋势。'
    await askQuestion(question)

    const answer = (await screen.findByText('本场比赛分析')).closest('article') as HTMLElement
    expect(answer).toBeTruthy()
    expect(screen.getByText('本场比赛分析已完成。')).toBeVisible()
    expect(screen.queryByText(`“${question}”`)).toBeNull()
    expect(screen.queryByText('本场比赛主题数据')).toBeNull()
    expect(screen.queryByText('已连接本场比赛上下文')).toBeNull()
    expect(screen.queryByText('结构化数据来自 Tennix 服务')).toBeNull()
  })

  it('keeps Home progress visible until done and then shows the complete answer', async () => {
    let releaseDone = () => {}
    const doneGate = new Promise<void>((resolve) => {
      releaseDone = resolve
    })
    streamChatMock.mockImplementation(() => {
      async function* generate(): AsyncGenerator<ChatEvent> {
        yield { type: 'status', payload: { stage: 'generating' } }
        yield { type: 'text_delta', payload: { delta: '正在整理事实。' } }
        await doneGate
        yield { type: 'text_delta', payload: { delta: '最终结论已完成。' } }
        yield { type: 'done', payload: { ok: true } }
      }
      return generate()
    })
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    await askQuestion('现在比赛情况如何？')

    expect(await screen.findByText('正在整理事实。')).toBeVisible()
    expect(screen.getByText('正在组织回答…')).toBeVisible()
    expect(screen.queryByText('最终结论已完成。')).toBeNull()

    releaseDone()

    expect(await screen.findByText(/最终结论已完成。/)).toBeVisible()
    await waitFor(() => expect(screen.queryByText('正在组织回答…')).toBeNull())
  })

  it('renders structured stream data and never parses the prose into a card', async () => {
    mockStream({
      data: { kind: 'matches', matches: [upcomingDto] },
      text: 'Sinner 今晚 20:30 出场。',
    })
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    await askQuestion('Sinner 今晚几点比赛？')

    expect(await screen.findByText('Sinner 今晚 20:30 出场。')).toBeVisible()
    expect(
      screen.getByRole('link', { name: /打开比赛：Sinner 对阵 Alcaraz/ }),
    ).toHaveAttribute('href', '/matches/mat_up1')
  })

  it('renders markdown prose instead of showing raw markers', async () => {
    mockStream({
      data: { kind: 'matches', matches: [upcomingDto] },
      text: '当前查到 **Qinwen Zheng**。\n\n- **对手**：Elena Rybakina\n- **赛事**：US Open',
    })
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    await askQuestion('Qinwen Zheng 下一场比赛是什么时候？')

    const answer = (await screen.findByText('结构化比赛结果')).closest('article') as HTMLElement
    expect(answer.querySelector('strong')?.textContent).toBe('Qinwen Zheng')
    expect(answer.querySelector('ul')).not.toBeNull()
    expect(answer.textContent).not.toContain('**')
  })

  it('keeps structured match cards in view after the markdown answer completes', async () => {
    mockStream({
      data: { kind: 'matches', matches: [upcomingDto] },
      text: [
        '当前查到 **Qinwen Zheng**。',
        '',
        '- **对手**：Elena Rybakina',
        '- **赛事**：US Open',
        '- **轮次**：Quarter-finals',
        '- **场地**：硬地',
        '- **赛制**：BO3',
      ].join('\n'),
    })
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    await askQuestion('Qinwen Zheng 下一场比赛是什么时候？')

    await screen.findByRole('link', { name: /打开比赛：Sinner 对阵 Alcaraz/ })
    await waitFor(() => {
      expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith(
        expect.objectContaining({ behavior: 'smooth', block: 'start' }),
      )
    })
  })

  it('triggers the initial question exactly once', async () => {
    render(<HomePage initialQuestion="Sinner 今晚几点比赛？" />)

    await waitFor(() => {
      expect(streamChatMock).toHaveBeenCalledTimes(1)
    })
    const [request] = streamChatMock.mock.calls[0]
    expect(request.messages).toEqual([{ role: 'user', content: 'Sinner 今晚几点比赛？' }])

    await screen.findByText('Sinner 今晚 20:30 出场。')
    expect(streamChatMock).toHaveBeenCalledTimes(1)
  })

  it('renders ambiguous candidates with internal player links', async () => {
    mockStream({
      data: {
        kind: 'player_resolution',
        matches: [],
        resolution: {
          status: 'ambiguous',
          query: 'Wang',
          player: null,
          candidates: [
            {
              player: { id: 'ply_wang_a', name: 'Xinyu Wang', localized_name: '王欣瑜', country_code: 'chn', ranking: 25 },
              matched_alias: 'Wang',
              alias_kind: 'surname',
              current_rank: 25,
            },
            {
              player: { id: 'ply_wang_b', name: 'Xiyu Wang', localized_name: '王曦雨', country_code: 'chn', ranking: 50 },
              matched_alias: 'Wang',
              alias_kind: 'surname',
              current_rank: 50,
            },
          ],
        },
      },
      text: '有多位 Wang，请选择其中一位。',
    })
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    await askQuestion('Wang 最近战绩如何？')

    expect(await screen.findByText('多位候选球员，请选择')).toBeVisible()
    expect(screen.getByRole('link', { name: /Xinyu Wang（王欣瑜）/ })).toHaveAttribute(
      'href',
      '/players/ply_wang_a',
    )
    expect(screen.getByRole('link', { name: /Xiyu Wang（王曦雨）/ })).toHaveAttribute(
      'href',
      '/players/ply_wang_b',
    )
  })

  it('renders broad historical unsupported without a card', async () => {
    mockStream({
      data: { kind: 'unsupported', matches: [] },
      text: 'P2 暂不支持大范围历史查询。',
    })
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    await askQuestion('Sinner 的全部历史战绩')

    expect(await screen.findByText('P2 暂不支持大范围历史查询。')).toBeVisible()
    expect(screen.queryByRole('link', { name: /打开比赛：Sinner 对阵/ })).toBeNull()
  })

  it('shows a visible stale badge for stale match data', async () => {
    const staleDto: MatchDto = {
      ...liveDto,
      freshness: { ...liveDto.freshness, is_stale: true, age_seconds: 240 },
    }
    mockStream({ data: { kind: 'matches', matches: [staleDto] }, text: '比分可能延迟。' })
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    await askQuestion('现在比分多少？')

    const staleLabels = await screen.findAllByText(/数据较旧 · 240 秒未刷新/)
    expect(staleLabels.length).toBeGreaterThan(0)
    expect(staleLabels[0]).toBeVisible()
  })

  it('disables duplicate submits while loading', async () => {
    streamChatMock.mockImplementation(() => {
      async function* generate(): AsyncGenerator<ChatEvent> {
        yield { type: 'status', payload: { stage: 'resolving' } }
        await new Promise(() => {})
      }
      return generate()
    })
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    const input = screen.getByLabelText('继续向 Tennix 提问')
    await userEvent.type(input, '今晚有比赛吗？')
    await userEvent.keyboard('{Enter}')

    const assistantForm = input.closest('form') as HTMLFormElement
    await waitFor(() => {
      expect(within(assistantForm).getByRole('button', { name: '发送问题' })).toBeDisabled()
    })
    expect(streamChatMock).toHaveBeenCalledTimes(1)
  })

  it('renders typed error copy with retry when the stream fails', async () => {
    mockStream({ errorCode: 'llm_unavailable' })
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    await askQuestion('今晚有比赛吗？')

    const errorCopies = await screen.findAllByText(/llm_unavailable/)
    expect(errorCopies.length).toBeGreaterThan(0)
    expect(errorCopies[0]).toBeVisible()
    expect(screen.getByRole('button', { name: '重试提问' })).toBeVisible()
  })

  it('renders optional data warnings without turning the answer into a terminal error', async () => {
    mockStream({
      data: { kind: 'matches', matches: [upcomingDto] },
      text: '比赛信息已找到。',
      warningMessage: '球员背景资料暂未提供。',
    })
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    await askQuestion('分析这场比赛和球员特点')

    expect(await screen.findByText('球员背景资料暂未提供。')).toBeVisible()
    expect(screen.queryByText('查询未完成')).toBeNull()
  })

  it('renders a friendly quota message with the retry interval', async () => {
    mockStream({ errorCode: 'rate_limited', errorDetails: { retry_after: '30' } })
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    await askQuestion('郑钦文下一场比赛是什么时候？')

    expect(await screen.findByText(/数据服务配额暂时用完/)).toBeVisible()
    expect(screen.getByText(/30 秒后重试/)).toBeVisible()
    expect(screen.getByRole('button', { name: '重试提问' })).toBeVisible()
  })

  it('never claims sample data is real', async () => {
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    expect(screen.queryByText('样例数据仅用于产品界面演示')).toBeNull()
    expect(screen.queryByText('5 场比赛')).toBeNull()
    expect(screen.queryByText('12 场比赛')).toBeNull()
    expect(screen.getByText('数据由 Tennix 服务提供 · 时间为北京时间')).toBeVisible()
  })

  it('shows follow-up placeholders instead of fabricated sections', async () => {
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    expect(screen.getByText('P1 暂不支持历史赛果')).toBeVisible()
    expect(screen.getByText('关注功能将在后续阶段接入')).toBeVisible()
    expect(screen.queryByText('正在比赛')).toBeNull()
    expect(screen.queryByText('第三盘 5–4')).toBeNull()
  })

  it('opens the featured match with the internal id route', async () => {
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    const featured = await screen.findByRole('link', { name: /打开比赛/ })
    expect(featured).toHaveAttribute('href', '/matches/mat_live1')
  })
})

describe('HomePage player history', () => {
  it('renders one history result with the bilingual player·scope title', async () => {
    mockStream({
      dataItems: [
        playerHistoryData({ player: sinnerPlayer, scope: 'last' }, [finishedHistoryDto]),
      ],
      text: '辛纳上一场比赛在 8 月 20 日。',
    })
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    await askQuestion('辛纳上一次比赛是什么时候？')

    expect(
      await screen.findByRole('heading', { name: 'Jannik Sinner（辛纳） · 上一场比赛' }),
    ).toBeVisible()
    const sections = screen.getAllByTestId('player-history-section')
    expect(sections).toHaveLength(1)
    expect(
      screen.getByRole('link', { name: /打开比赛：Sinner 对阵 One/ }),
    ).toHaveAttribute('href', '/matches/mat_hist_1')
    expect(screen.queryByText('没有符合条件的比赛')).toBeNull()
  })

  it('renders yesterday and season scope labels', async () => {
    mockStream({
      dataItems: [
        playerHistoryData({ player: sinnerPlayer, scope: 'yesterday' }),
      ],
      text: '昨天没有比赛。',
    })
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')
    await askQuestion('Sinner 昨天赢了吗？')

    expect(
      await screen.findByRole('heading', { name: 'Jannik Sinner（辛纳） · 昨日赛果' }),
    ).toBeVisible()
    expect(screen.getByText('该范围暂无赛果信息')).toBeVisible()
    expect(screen.queryByText('没有符合条件的比赛')).toBeNull()
  })

  it('renders multiple history sections simultaneously with the shared title', async () => {
    mockStream({
      dataItems: [
        playerHistoryData({ player: sinnerPlayer, scope: 'recent' }, [finishedHistoryDto]),
        playerHistoryData({
          player: zhengPlayer,
          scope: 'recent',
          empty_reason: 'no_results_in_scope',
        }),
      ],
      text: '已整理两位球员的赛果。',
    })
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    await askQuestion('辛纳最近赛果如何？郑钦文赛果如何？')

    expect(await screen.findByRole('heading', { name: '球员赛果与战绩' })).toBeVisible()
    const sections = screen.getAllByTestId('player-history-section')
    expect(sections).toHaveLength(2)
    // The empty player must not hide the other player's matches.
    expect(sections[0]).toHaveAttribute('aria-label', 'Jannik Sinner（辛纳） 近期赛果')
    expect(sections[1]).toHaveAttribute('aria-label', 'Qinwen Zheng（郑钦文） 近期赛果')
    expect(
      within(sections[0]).getByRole('link', { name: /打开比赛：Sinner 对阵 One/ }),
    ).toHaveAttribute('href', '/matches/mat_hist_1')
    expect(within(sections[1]).getByText('该范围暂无赛果信息')).toBeVisible()
    expect(screen.queryByText('没有符合条件的比赛')).toBeNull()
  })

  it('renders season wins, losses, win rate, titles and only available surfaces', async () => {
    mockStream({
      dataItems: [
        playerHistoryData({
          player: zhengPlayer,
          scope: 'season',
          season: 2026,
          season_record: {
            season: 2026,
            matches_won: 30,
            matches_lost: 5,
            titles: 4,
            hard: { won: 20, lost: 3 },
            clay: null,
            grass: { won: 10, lost: 2 },
          },
        }),
      ],
      text: '郑钦文本赛季 30 胜 5 负。',
    })
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    await askQuestion('郑钦文这个赛季战绩如何？')

    expect(
      await screen.findByRole('heading', { name: 'Qinwen Zheng（郑钦文） · 2026 赛季战绩' }),
    ).toBeVisible()
    const summary = screen.getByTestId('season-record-summary')
    expect(within(summary).getByText('30')).toBeVisible()
    expect(within(summary).getByText('5')).toBeVisible()
    expect(within(summary).getByText('86%')).toBeVisible()
    expect(within(summary).getByText('4')).toBeVisible()
    const surfaces = screen.getAllByTestId('season-surface-record')
    expect(surfaces).toHaveLength(2)
    expect(surfaces[0].textContent).toContain('硬地')
    expect(surfaces[0].textContent).toContain('20-3')
    expect(surfaces[1].textContent).toContain('草地')
    expect(summary.textContent).not.toContain('红土')
  })

  it('renders the unavailable season copy for a missing record', async () => {
    mockStream({
      dataItems: [
        playerHistoryData({
          player: zhengPlayer,
          scope: 'season',
          season: 2024,
          availability: 'unavailable',
          empty_reason: 'season_record_unavailable',
        }),
      ],
      text: '该赛季战绩暂不可用。',
    })
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    await askQuestion('郑钦文 2024 赛季战绩如何？')

    expect(
      await screen.findByRole('heading', { name: 'Qinwen Zheng（郑钦文） · 2024 赛季战绩' }),
    ).toBeVisible()
    expect(screen.getByText('该赛季战绩暂不可用')).toBeVisible()
    expect(screen.queryByText('没有符合条件的比赛')).toBeNull()
  })

  it('fills the follow-up prompt from a history match card', async () => {
    mockStream({
      dataItems: [
        playerHistoryData({ player: sinnerPlayer, scope: 'last' }, [finishedHistoryDto]),
      ],
      text: '辛纳上一场比赛在 8 月 20 日。',
    })
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    await askQuestion('辛纳上一次比赛是什么时候？')

    const followUp = await screen.findByRole('button', { name: '继续追问' })
    await userEvent.click(followUp)

    const input = screen.getByLabelText('继续向 Tennix 提问') as HTMLInputElement
    expect(input.value).toContain('Sinner 对阵 One')
  })
})
