import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { MatchPage } from './match-page'
import { buildPreviewMatch } from './match/match-preview-data'
import type { ChatEvent, MatchDto, MatchSnapshotDto, StructuredData } from '@/lib/api/types'

const { getMatchSnapshotMock, openMatchStreamMock, streamChatMock } = vi.hoisted(() => ({
  getMatchSnapshotMock: vi.fn(),
  openMatchStreamMock: vi.fn(),
  streamChatMock: vi.fn(),
}))

vi.mock('@/lib/api/client', () => ({
  getMatchSnapshot: getMatchSnapshotMock,
  openMatchStream: openMatchStreamMock,
  parseMatchStream: async function* parseMatchStreamMock() {
    await new Promise(() => {})
  },
  getMatches: vi.fn(),
  getPlayers: vi.fn(),
  streamChat: streamChatMock,
}))

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

function wrapSnapshot(match: MatchDto): MatchSnapshotDto {
  return {
    match,
    points: [],
    statistics: [],
    momentum: [],
    quality: [],
    state_version: 1,
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

function mockStream(options: { data?: StructuredData; text?: string; errorCode?: string }) {
  streamChatMock.mockImplementation(() => {
    async function* generate(): AsyncGenerator<ChatEvent> {
      yield { type: 'status', payload: { stage: 'resolving' } }
      if (options.data) yield { type: 'data', payload: options.data }
      if (options.text) yield { type: 'text_delta', payload: { delta: options.text } }
      if (options.errorCode) {
        yield { type: 'error', payload: { code: options.errorCode, message: 'failed', details: {} } }
      } else {
        yield { type: 'done', payload: { ok: true } }
      }
    }
    return generate()
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  Element.prototype.scrollIntoView = vi.fn()
  nextMatch = makeMatch()
  getMatchSnapshotMock.mockImplementation(async () => wrapSnapshot(nextMatch as MatchDto))
  openMatchStreamMock.mockResolvedValue(new Response(null, { status: 200 }))
  mockStream({ data: { kind: 'match', matches: [makeMatch()] }, text: 'Sinner 正在发球。' })
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

  it('shows unavailable copy for missing round, surface, and server', async () => {
    nextMatch =
      makeMatch({ round: null, surface: null, indoor: null, live_state: { score: null, server_player_id: null } })

    render(<MatchPage matchId="mat_1" />)

    await screen.findByText('Jannik Sinner')
    expect(screen.getAllByText('暂未提供').length).toBeGreaterThan(0)
  })

  it('shows the stale indicator', async () => {
    nextMatch =
      makeMatch({ freshness: { provider: 'fake', source_updated_at: null, observed_at: '2026-09-08T10:00:00Z', is_stale: true, age_seconds: 180 } })

    render(<MatchPage matchId="mat_1" />)

    expect(await screen.findAllByText(/数据较旧 · 180 秒未刷新/)).not.toHaveLength(0)
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

    expect(await screen.findByText(/比赛不存在/)).toBeVisible()
  })

  it('renders provider errors with retry', async () => {
    getMatchSnapshotMock.mockRejectedValue(
      Object.assign(new Error('down'), { code: 'provider_unavailable', status: 503 }),
    )

    render(<MatchPage matchId="mat_1" />)

    expect(await screen.findByText(/provider_unavailable/)).toBeVisible()
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

    expect(screen.getByText('ACE 球')).toBeVisible()
    expect(screen.getByRole('button', { name: /第 1 盘/ })).toBeVisible()
    expect(screen.queryByText('P2 数据暂不可用')).toBeNull()
  })

  it('keeps honest missing copy when the snapshot carries no statistics or points', async () => {
    render(<MatchPage matchId="mat_1" />)
    await screen.findByText('Jannik Sinner')

    expect(screen.getByText(/技术统计暂未提供/)).toBeVisible()
    expect(screen.getByText(/逐分数据暂未提供/)).toBeVisible()
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
    expect(screen.getByText(/Sinner \+14/)).toBeVisible()
    expect(screen.getByText('样例数据仅用于产品界面演示')).toBeVisible()
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
