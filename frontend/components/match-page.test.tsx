import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { MatchPage } from './match-page'
import { buildPreviewMatch } from './match/match-preview-data'
import type { ChatEvent, MatchDto, MatchSnapshotDto, StructuredData } from '@/lib/api/types'

const {
  getMatchSnapshotMock,
  openMatchStreamMock,
  streamChatMock,
  getMatchDecisionMock,
  openDecisionStreamMock,
  parseDecisionStreamMock,
} = vi.hoisted(() => ({
  getMatchSnapshotMock: vi.fn(),
  openMatchStreamMock: vi.fn(),
  streamChatMock: vi.fn(),
  getMatchDecisionMock: vi.fn(),
  openDecisionStreamMock: vi.fn(),
  parseDecisionStreamMock: vi.fn(),
}))

vi.mock('@/lib/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api/client')>()
  return {
    ...actual,
    getMatchSnapshot: getMatchSnapshotMock,
    openMatchStream: openMatchStreamMock,
    parseMatchStream: async function* parseMatchStreamMock() {
      await new Promise(() => {})
    },
    getMatches: vi.fn(),
    getPlayers: vi.fn(),
    streamChat: streamChatMock,
    getMatchDecision: getMatchDecisionMock,
    openDecisionStream: openDecisionStreamMock,
    parseDecisionStream: parseDecisionStreamMock,
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
  usePathname: () => '/matches/mat_1',
  useSearchParams: () => new URLSearchParams(),
}))

let nextMatch: MatchDto | null = null

function wrapSnapshot(match: MatchDto, stateVersion = 1): MatchSnapshotDto {
  return {
    match,
    points: [],
    statistics: [],
    momentum: [],
    quality: [],
    state_version: stateVersion,
    as_of: match.freshness.observed_at,
  }
}

function makeMatch(overrides: Partial<MatchDto> = {}): MatchDto {
  return {
    id: 'mat_1',
    status: 'live',
    players: [
      { id: 'ply_1', name: 'Jannik Sinner', country_code: 'ita', ranking: 1 },
      { id: 'ply_2', name: 'Carlos Alcaraz', country_code: 'esp', ranking: 2 },
    ],
    tournament: { id: 'trn_1', name: 'ATP Finals', tour: 'atp' },
    scheduled_at: '2026-09-08T10:00:00Z',
    round: 'Semifinal',
    surface: 'hard',
    indoor: true,
    format: 'BO3',
    live_state: {
      current_set_number: 3,
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
    ...overrides,
  }
}

function mockStream(options: {
  data?: StructuredData
  text?: string
  errorCode?: string
  warningMessage?: string
}) {
  streamChatMock.mockImplementation(() => {
    async function* generate(): AsyncGenerator<ChatEvent> {
      yield { type: 'status', payload: { stage: 'resolving' } }
      if (options.data) yield { type: 'data', payload: options.data }
      if (options.text) yield { type: 'text_delta', payload: { delta: options.text } }
      if (options.warningMessage) {
        yield {
          type: 'warning',
          payload: { code: 'optional_data_unavailable', message: options.warningMessage, details: {} },
        }
      }
      if (options.errorCode) {
        yield { type: 'error', payload: { code: options.errorCode, message: 'failed', details: {} } }
      } else {
        yield { type: 'done', payload: { ok: true } }
      }
    }
    return generate()
  })
}

async function notFoundDecision() {
  const { ApiError } = await import('@/lib/api/client')
  throw new ApiError(404, 'not_found', 'No P3 decision context for this match')
}

function parkedStreamResponse(): Response {
  return new Response(new ReadableStream({ start() {} }), {
    status: 200,
    headers: { 'content-type': 'text/event-stream' },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  Element.prototype.scrollIntoView = vi.fn()
  nextMatch = makeMatch()
  getMatchSnapshotMock.mockImplementation(async () => wrapSnapshot(nextMatch as MatchDto))
  openMatchStreamMock.mockResolvedValue(new Response(null, { status: 200 }))
  mockStream({ data: { kind: 'match', matches: [makeMatch()] }, text: 'Sinner 正在发球。' })
  // Default: no P3 decision context → the classic P2 layout stays.
  getMatchDecisionMock.mockImplementation(notFoundDecision)
  openDecisionStreamMock.mockResolvedValue(parkedStreamResponse())
  parseDecisionStreamMock.mockImplementation(async function* parked() {
    await new Promise(() => {})
  })
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('production match page', () => {
  it('keeps the current match context out of the user prompt', async () => {
    render(<MatchPage matchId="mat_1" />)
    await screen.findByText('Jannik Sinner')

    await userEvent.type(screen.getByLabelText('向 Tennix 询问本场比赛'), '谁在发球？')
    await userEvent.keyboard('{Enter}')

    await waitFor(() => {
      expect(streamChatMock).toHaveBeenCalled()
    })
    expect(streamChatMock).toHaveBeenCalledWith(
      expect.objectContaining({
        scope: 'match',
        match_id: 'mat_1',
        messages: expect.arrayContaining([{ role: 'user', content: '谁在发球？' }]),
      }),
      expect.anything(),
    )
    const request = streamChatMock.mock.calls[0][0]
    expect(request.messages).toEqual([{ role: 'user', content: '谁在发球？' }])
  })

  it('maps upcoming hero state', async () => {
    const scheduled = makeMatch({
      status: 'scheduled',
      scheduled_at: '2026-09-08T12:30:00Z',
      live_state: null,
    })
    nextMatch = scheduled
    mockStream({ data: { kind: 'match', matches: [scheduled] }, text: '比赛今晚开始。' })

    render(<MatchPage matchId="mat_1" />)

    expect(await screen.findByText('Jannik Sinner 对阵 Carlos Alcaraz')).toBeVisible()
    const statusBadge = document.querySelector('[role="status"]')
    expect(statusBadge?.textContent).toContain('即将开始')
    expect(screen.getByText('20:30')).toBeVisible()
  })

  it('shows production player flags and country codes in the match hero', async () => {
    const scheduled = makeMatch({
      status: 'scheduled',
      live_state: null,
    })
    nextMatch = scheduled

    render(<MatchPage matchId="mat_1" />)

    await screen.findByText('Jannik Sinner 对阵 Carlos Alcaraz')
    expect(screen.getByRole('img', { name: '意大利国旗' })).toBeVisible()
    expect(screen.getByRole('img', { name: '西班牙国旗' })).toBeVisible()
    expect(screen.getAllByText('ITA').length).toBeGreaterThan(0)
    expect(screen.getAllByText('ESP').length).toBeGreaterThan(0)
  })

  it('maps live hero state with server highlighting', async () => {
    render(<MatchPage matchId="mat_1" />)

    await screen.findByText('Jannik Sinner')
    const badges = Array.from(document.querySelectorAll('[role="status"]'))
    expect(badges.some((badge) => badge.textContent?.includes('直播'))).toBe(true)
    const server = document.getElementById('server-indicator')
    expect(server).not.toBeNull()
    expect(server?.textContent).toContain('当前发球')
    expect(screen.getAllByText('当前发球').length).toBeGreaterThan(0)
  })

  it('uses the provider current set when score rows are incomplete', async () => {
    nextMatch = makeMatch({
      live_state: {
        current_set_number: 3,
        score: {
          sets_won: [1, 1],
          sets: [
            { number: 1, player1_games: 6, player2_games: 4 },
            { number: 2, player1_games: 4, player2_games: 6 },
          ],
          points: ['30', '15'],
          is_tiebreak: false,
        },
        server_player_id: 'ply_1',
      },
    })

    render(<MatchPage matchId="mat_1" />)

    await screen.findByText('Jannik Sinner')
    expect(screen.getAllByText('第 3 盘')).toHaveLength(2)
    expect(screen.queryAllByText('第 2 盘')).toHaveLength(0)
    const liveTable = screen.getByRole('table', { name: '实时比赛比分' })
    expect(within(liveTable).getByRole('columnheader', { name: '2' })).not.toHaveClass('text-primary')
  })

  it('does not infer the current set from the number of score rows', async () => {
    nextMatch = makeMatch({
      live_state: {
        current_set_number: null,
        score: {
          sets_won: [1, 1],
          sets: [
            { number: 1, player1_games: 6, player2_games: 4 },
            { number: 2, player1_games: 4, player2_games: 6 },
          ],
          points: ['30', '15'],
          is_tiebreak: false,
        },
        server_player_id: 'ply_1',
      },
    })

    render(<MatchPage matchId="mat_1" />)

    await screen.findByText('Jannik Sinner')
    expect(screen.getByText('盘数暂未提供')).toBeVisible()
    expect(screen.queryAllByText('第 2 盘')).toHaveLength(0)
    const liveTable = screen.getByRole('table', { name: '实时比赛比分' })
    expect(within(liveTable).getByRole('columnheader', { name: '2' })).not.toHaveClass('text-primary')
  })

  it('does not claim both players are receiving when the server is unknown', async () => {
    nextMatch = makeMatch({
      live_state: { score: null, server_player_id: null },
    })

    render(<MatchPage matchId="mat_1" />)

    await screen.findByText('Jannik Sinner')
    expect(screen.queryAllByText('接发球')).toHaveLength(0)
    expect(screen.getAllByText('发球方暂未提供')).toHaveLength(2)
  })

  it('does not invent a set label when a live snapshot has no set rows', async () => {
    nextMatch = makeMatch({
      live_state: {
        score: {
          sets_won: [0, 0],
          sets: [],
          points: ['15', '0'],
          is_tiebreak: false,
        },
        server_player_id: 'ply_1',
      },
    })

    render(<MatchPage matchId="mat_1" />)

    await screen.findByText('Jannik Sinner')
    expect(screen.getByText('当前局 15–0')).toBeVisible()
    expect(screen.queryAllByText(/第\s*0\s*盘/)).toHaveLength(0)
    expect(screen.queryByText(/第-盘|第\d+盘 -–-/)).toBeNull()
  })

  it('maps finished hero state with winner', async () => {
    nextMatch =
      makeMatch({
        status: 'finished',
        winner_player_id: 'ply_1',
        live_state: {
          score: {
            sets_won: [2, 1],
            sets: [
              { number: 1, player1_games: 6, player2_games: 4 },
              { number: 2, player1_games: 4, player2_games: 6 },
              { number: 3, player1_games: 6, player2_games: 3 },
            ],
            points: [null, null],
            is_tiebreak: false,
          },
          server_player_id: null,
        },
      })

    render(<MatchPage matchId="mat_1" />)

    expect(await screen.findByText('Jannik Sinner 击败 Carlos Alcaraz')).toBeVisible()
    expect(screen.getAllByText('胜者').length).toBeGreaterThan(0)
  })

  it('shows tiebreak points in both finished match scoreboards', async () => {
    nextMatch = makeMatch({
      status: 'finished',
      winner_player_id: 'ply_1',
      live_state: {
        current_set_number: null,
        score: {
          sets_won: [2, 0],
          sets: [
            {
              number: 1,
              player1_games: 7,
              player2_games: 6,
              player1_tiebreak_points: 7,
              player2_tiebreak_points: 5,
            },
            { number: 2, player1_games: 6, player2_games: 4 },
          ],
          points: [null, null],
          is_tiebreak: false,
        },
        server_player_id: null,
      },
    })

    render(<MatchPage matchId="mat_1" />)

    const heroTable = await screen.findByRole('table', { name: '最终比赛比分' })
    expect(within(heroTable).getByText('7（7）')).toBeVisible()
    expect(within(heroTable).getByText('6（5）')).toBeVisible()
    const detailTable = screen.getByRole('table', { name: '最终详细比分' })
    expect(within(detailTable).getByText('7（7）')).toBeVisible()
    expect(within(detailTable).getByText('6（5）')).toBeVisible()
    expect(screen.getAllByText(/最终比分 7–6（7–5）/).length).toBeGreaterThan(0)
  })

  it('shows unavailable copy for missing round, surface, and server', async () => {
    nextMatch =
      makeMatch({ round: null, surface: null, indoor: null, live_state: { score: null, server_player_id: null } })

    render(<MatchPage matchId="mat_1" />)

    await screen.findByText('Jannik Sinner')
    expect(screen.getAllByText(/暂未提供|暂缺|暂无/).length).toBeGreaterThan(0)
  })

  it('does not describe an unconfirmed match as waiting to start', async () => {
    nextMatch = makeMatch({ status: 'unknown', live_state: null })

    render(<MatchPage matchId="mat_1" />)

    expect(await screen.findAllByText('比赛信息待更新')).not.toHaveLength(0)
    expect(screen.getByText('目前无法获取这场比赛的比分，请稍后再看。')).toBeVisible()
    expect(screen.queryByText('比赛开始后，这里会显示每盘比分、当前局分和发球方。')).toBeNull()
  })

  it('shows the stale indicator', async () => {
    nextMatch =
      makeMatch({ freshness: { provider: 'fake', source_updated_at: null, observed_at: '2026-09-08T10:00:00Z', is_stale: true, age_seconds: 180 } })

    render(<MatchPage matchId="mat_1" />)

    expect(await screen.findAllByText(/数据可能延迟 · 3 分钟前/)).not.toHaveLength(0)
  })

  it('refresh reloads the match exactly once more', async () => {
    render(<MatchPage matchId="mat_1" />)
    await screen.findByText('Jannik Sinner')
    expect(getMatchSnapshotMock).toHaveBeenCalledTimes(1)

    await userEvent.click(screen.getByRole('button', { name: '刷新比赛数据' }))

    await waitFor(() => {
      expect(getMatchSnapshotMock).toHaveBeenCalledTimes(2)
    })
  })

  it('renders a not-found state for unknown matches', async () => {
    getMatchSnapshotMock.mockRejectedValue(
      Object.assign(new Error('Match not found'), { code: 'not_found', status: 404 }),
    )

    render(<MatchPage matchId="mat_missing" />)

    expect(await screen.findByText('未找到这场比赛')).toBeVisible()
    expect(screen.getByText(/比赛可能已结束，或此链接已失效/)).toBeVisible()
    expect(screen.getByRole('link', { name: '返回首页' })).toHaveAttribute('href', '/')
    expect(screen.queryByText(/内部 ID|进程重启/)).toBeNull()
  })

  it('renders provider errors with retry', async () => {
    getMatchSnapshotMock.mockRejectedValue(
      Object.assign(new Error('down'), { code: 'provider_unavailable', status: 503 }),
    )

    render(<MatchPage matchId="mat_1" />)

    expect(await screen.findByText('比赛详情暂时无法加载，请稍后重试。')).toBeVisible()
    expect(screen.queryByText(/provider_unavailable/)).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: '重试加载比赛' }))

    await waitFor(() => {
      expect(getMatchSnapshotMock).toHaveBeenCalledTimes(2)
    })
  })

  it('renders live statistics and points from the snapshot in production', async () => {
    const live = makeMatch()
    nextMatch = live
    getMatchSnapshotMock.mockImplementation(async () => ({
      ...wrapSnapshot(live),
      statistics: [
        {
          match_id: 'mat_1',
          name: 'aces',
          period: 'match',
          player1_value: 8,
          player2_value: 5,
          unit: null,
          provenance: 'provider',
          availability: 'available',
          as_of: '2026-09-08T10:00:00Z',
        },
      ],
      points: [
        {
          id: 'pe_1',
          match_id: 'mat_1',
          sequence: 1,
          set_number: 1,
          game_number: 1,
          point_number: 1,
          server_player_id: 'ply_1',
          winner_player_id: 'ply_1',
          score_before: null,
          score_after: {
            sets_won: [0, 0],
            sets: [],
            points: ['15', '0'],
            is_tiebreak: false,
          },
          is_break_point: false,
          is_set_point: false,
          is_match_point: false,
          observed_at: '2026-09-08T10:00:00Z',
          provider: 'fake',
          source_fingerprint: 'fp-1',
          revision: 1,
          quality: null,
        },
      ],
    }))

    render(<MatchPage matchId="mat_1" />)
    await screen.findByText('Jannik Sinner')

    expect(screen.getByText(/ACE 球/)).toBeVisible()
    expect(screen.getByRole('button', { name: /第 1 盘/ })).toBeVisible()
    expect(screen.queryByText('P2 数据暂不可用')).toBeNull()
  })

  it('keeps honest missing copy when the snapshot carries no statistics or points', async () => {
    render(<MatchPage matchId="mat_1" />)
    await screen.findByText('Jannik Sinner')

    expect(screen.getByText(/本场比赛暂未提供技术统计/)).toBeVisible()
    expect(screen.getByText(/本场比赛暂无逐分记录/)).toBeVisible()
    expect(screen.queryByText(/供应商|P2 数据/)).toBeNull()
    expect(screen.queryByText('一发成功率')).toBeNull()
    expect(screen.queryByText(/Sinner \+14/)).toBeNull()
  })

  it('renders contextual prose from the stream without inventing cards', async () => {
    render(<MatchPage matchId="mat_1" />)
    await screen.findByText('Jannik Sinner')

    await userEvent.type(screen.getByLabelText('向 Tennix 询问本场比赛'), '谁在发球？')
    await userEvent.keyboard('{Enter}')

    expect(await screen.findByText('Sinner 正在发球。')).toBeVisible()
  })

  it('keeps internal prompt and context labels out of the user-facing analysis card', async () => {
    mockStream({
      data: { kind: 'intelligence', matches: [] },
      text: '本场比赛分析已完成。',
    })
    render(<MatchPage matchId="mat_1" />)
    await screen.findByText('Jannik Sinner')

    const question = '根据本场数据分析趋势。'
    await userEvent.type(screen.getByLabelText('向 Tennix 询问本场比赛'), question)
    await userEvent.keyboard('{Enter}')

    expect(await screen.findByText('本场比赛分析')).toBeVisible()
    expect(screen.getByText('本场比赛分析已完成。')).toBeVisible()
    expect(screen.queryByText(`“${question}”`)).toBeNull()
    expect(screen.queryByText('本场比赛主题数据')).toBeNull()
    expect(screen.queryByText('已连接本场比赛上下文')).toBeNull()
  })

  it('renders optional data warnings without showing a terminal query error', async () => {
    mockStream({
      data: { kind: 'match', matches: [makeMatch()] },
      text: '当前比赛分析已完成。',
      warningMessage: '球员背景资料暂未提供。',
    })
    render(<MatchPage matchId="mat_1" />)
    await screen.findByText('Jannik Sinner')

    await userEvent.type(screen.getByLabelText('向 Tennix 询问本场比赛'), '分析当前比赛和球员特点')
    await userEvent.keyboard('{Enter}')

    expect(await screen.findByText('球员背景资料暂未提供。')).toBeVisible()
    expect(screen.queryByText('查询未完成')).toBeNull()
  })

  it('keeps completed prose immutable and explains its frozen snapshot after a newer update', async () => {
    const live = makeMatch()
    getMatchSnapshotMock.mockImplementation(async () => wrapSnapshot(live, 2))
    mockStream({
      data: {
        kind: 'match',
        matches: [live],
        answer_context: {
          match_id: 'mat_1',
          state_version: 1,
          as_of: '2026-09-08T10:00:00Z',
        },
      },
      text: '回答基于版本 1。',
    })

    render(<MatchPage matchId="mat_1" />)
    await screen.findByText('Jannik Sinner')

    await userEvent.type(screen.getByLabelText('向 Tennix 询问本场比赛'), '当前比分是多少？')
    await userEvent.keyboard('{Enter}')

    expect(await screen.findByText('回答基于版本 1。')).toBeVisible()
    expect(screen.getByText(/比赛在回答期间更新/)).toBeVisible()
    expect(screen.queryByText(/请重新提问/)).toBeNull()
  })

  it('renders contextual markdown instead of showing raw markers', async () => {
    mockStream({
      data: { kind: 'match', matches: [makeMatch()] },
      text: '当前比赛为 **ATP Finals**。\n\n- **场地**：硬地\n- **赛制**：BO3',
    })
    render(<MatchPage matchId="mat_1" />)
    await screen.findByText('Jannik Sinner')

    await userEvent.type(screen.getByLabelText('向 Tennix 询问本场比赛'), '这是什么赛事？')
    await userEvent.keyboard('{Enter}')

    const answer = await screen.findByRole('article')
    expect(answer.querySelector('strong')?.textContent).toBe('ATP Finals')
    expect(answer.querySelector('ul')).not.toBeNull()
    expect(answer.textContent).not.toContain('**')
  })
})

describe('prototype preview route', () => {
  it('still renders the original prototype preview with sample data', async () => {
    render(<MatchPage previewMatch={buildPreviewMatch('live')} preview />)

    expect(await screen.findByText('Jannik Sinner')).toBeVisible()
    expect(screen.getByText('比赛状态预览')).toBeVisible()
    expect(screen.getByText('一发成功率')).toBeVisible()
    expect(screen.getByText(/Sinner 最近 7 个短回合中赢下 5 分/)).toBeVisible()
    expect(screen.getByText('样例数据仅供参考，不代表实时比赛')).toBeVisible()
  })

  it('switches preview status without touching the backend', async () => {
    render(<MatchPage previewMatch={buildPreviewMatch('live')} preview />)
    await screen.findByText('Jannik Sinner')

    await userEvent.click(screen.getByRole('button', { name: '即将开始' }))

    await waitFor(() => {
      expect(screen.getByText('比赛状态预览')).toBeVisible()
    })
    expect(getMatchSnapshotMock).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// T69: production decision workbench.
// ---------------------------------------------------------------------------

import type { DecisionSnapshotDto } from '@/lib/api/types'

function workbenchDecision(overrides: Partial<DecisionSnapshotDto> = {}): DecisionSnapshotDto {
  return {
    match_id: 'mat_1',
    market_id: 'mkt_1',
    action: 'hold',
    reason_code: null,
    target_player_id: 'ply_1',
    observation_version: 3,
    model_probabilities: { ply_1: 0.62, ply_2: 0.38 },
    model_availability: 'available',
    quote_average_price: '0.525',
    quote_side: 'exit',
    conservative_net_edge: '0.0400',
    max_acceptable_price: null,
    hold_value: '10.80',
    model_version: 'prematch-elo-v1',
    calibration_version: 'platt-v1',
    policy_version: 'policy-v1',
    data_version: 'apidata-v1',
    gates: [{ gate: 'net_edge', passed: true, reason_code: null }],
    outcome_levels: [
      { player_id: 'ply_1', best_bid: '0.55', best_ask: '0.57' },
      { player_id: 'ply_2', best_bid: '0.43', best_ask: '0.45' },
    ],
    position: {
      position_id: 'pos_1',
      outcome_player_id: 'ply_1',
      status: 'open',
      entry_cost: '10.00',
      shares: '19.05',
      average_entry_price: '0.525',
      current_exit_value: '11.40',
      net_pnl: null,
      events: [
        { id: 'e1', kind: 'entry_intent', at: '2026-09-08T10:00:00Z', reason_code: null },
        { id: 'e2', kind: 'entry_fill', at: '2026-09-08T10:00:20Z', reason_code: null },
      ],
    },
    lifecycle: ['entry_pending', 'filled'],
    is_stale: false,
    has_gap: false,
    lock_profit_available: false,
    as_of: '2026-09-08T10:00:00Z',
    ...overrides,
  }
}

function sectionLabels(container: Element): (string | null)[] {
  return Array.from(container.children).map((child) => {
    const heading = child.querySelector('h2')
    return heading ? heading.textContent : child.getAttribute('aria-label')
  })
}

describe('production decision workbench (T69)', () => {
  beforeEach(() => {
    getMatchDecisionMock.mockResolvedValue(workbenchDecision())
  })

  it('renders exactly one full-width DecisionSummary outside the content grid', async () => {
    const { container } = render(<MatchPage matchId="mat_1" />)

    await waitFor(() =>
      expect(container.querySelectorAll('#decision-summary-title')).toHaveLength(1),
    )
    const content = container.querySelector('#content')!
    expect(content.querySelector('#decision-summary-title')).toBeNull()
    const summary = container.querySelector('#decision-summary-title')!
    expect(
      summary.compareDocumentPosition(content) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
  })

  it('keeps the live decision page consumer-facing and collapses audit metadata', async () => {
    const { container } = render(<MatchPage matchId="mat_1" />)

    await screen.findByText('判断依据')
    expect(screen.getByText('关注球员')).toBeVisible()
    expect(screen.getByText('判断把握')).toBeVisible()
    expect(screen.queryByText(/研究方向|模型状态|暂不在模型范围内/)).toBeNull()
    expect(screen.getByText('影响本次判断的因素')).toBeVisible()
    expect(screen.getByText('查看判断细节')).toBeVisible()
    const evidence = container.querySelector('[aria-labelledby="decision-evidence-title"]')!
    const details = evidence.querySelector('details')!
    expect(details).not.toHaveAttribute('open')
    expect(screen.queryByText('prematch-elo-v1')).toBeNull()
    expect(container.textContent).not.toMatch(/P3 BETA|Decision Evidence|Paper lifecycle|hard gates|freshness|STALE|DATA GAP|FOK|P&L/i)
    await userEvent.click(screen.getByText('查看判断细节'))
    expect(screen.queryByText('prematch-elo-v1')).toBeNull()
    expect(screen.getByText(/本次判断时间/)).toBeVisible()
  })

  it('follows the frozen mobile DOM order inside the content grid', async () => {
    const { container } = render(<MatchPage matchId="mat_1" />)

    const content = await waitFor(() => {
      const element = container.querySelector('#content')!
      expect(sectionLabels(element)).toHaveLength(9)
      return element
    })
    expect(sectionLabels(content)).toEqual([
      '比分与比赛进程',
      '关键事实',
      '比赛概览',
      '胜率与市场价格走势',
      '判断依据',
      '技术统计',
      '得分走势与关键分',
      '模拟交易记录',
      '本场比赛助手',
    ])
  })

  it('removes the legacy MarketCard and the duplicate AI insight card', async () => {
    render(<MatchPage matchId="mat_1" />)

    await waitFor(() => expect(screen.getByText('胜率与市场价格走势')).toBeTruthy())
    expect(screen.queryByRole('heading', { name: '本场市场信息' })).toBeNull()
    expect(screen.queryByText('本场比赛问题建议')).toBeNull()
  })

  it('preserves the P2 score, stats, PBP and assistant sections', async () => {
    render(<MatchPage matchId="mat_1" />)

    await waitFor(() => expect(screen.getByText('胜率与市场价格走势')).toBeTruthy())
    for (const heading of [
      '比赛概览',
      '比分与比赛进程',
      '技术统计',
      '得分走势与关键分',
      '本场比赛助手',
      '关键事实',
    ]) {
      expect(screen.getByText(heading)).toBeTruthy()
    }
  })

  it('surfaces decision-stream degradation without touching the sports stream', async () => {
    // A gap delta (version 99 after 3) degrades the decision stream; the
    // failing refetch keeps the last trusted snapshot visible.
    parseDecisionStreamMock.mockImplementation(async function* gap() {
      yield {
        type: 'decision_delta',
        id: '99',
        payload: {
          type: 'decision_delta',
          match_id: 'mat_1',
          observation_version: 99,
          action: 'hold',
          as_of: '2026-09-08T10:00:00Z',
        },
      }
      await new Promise(() => {})
    })
    getMatchDecisionMock
      .mockResolvedValueOnce(workbenchDecision())
      .mockRejectedValue(new Error('decision rest boom'))

    render(<MatchPage matchId="mat_1" />)

    await waitFor(() =>
      expect(screen.getByText(/判断暂时无法更新，仍显示最近一次结果/)).toBeTruthy(),
    )
    expect(screen.getByText(/比赛实时比分不受影响/)).toBeTruthy()
    // The last trusted workbench view stays rendered.
    expect(screen.getByText('胜率与市场价格走势')).toBeTruthy()
  })

  it('keeps the P2 layout minus MarketCard without decision context', async () => {
    getMatchDecisionMock.mockImplementation(notFoundDecision)
    render(<MatchPage matchId="mat_1" />)

    await waitFor(() => expect(screen.getByText('比赛概览')).toBeTruthy())
    expect(screen.queryByText('市场智能')).toBeNull()
    expect(screen.queryByText('胜率与市场价格走势')).toBeNull()
    expect(screen.getByText('本场比赛问题建议')).toBeTruthy()
  })
})
