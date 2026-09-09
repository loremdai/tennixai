import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { HomePage } from './home-page'
import type { ChatEvent, MatchDto, StructuredData } from '@/lib/api/types'

const { getMatchesMock, getPlayersMock, getMatchMock, streamChatMock } = vi.hoisted(() => ({
  getMatchesMock: vi.fn(),
  getPlayersMock: vi.fn(),
  getMatchMock: vi.fn(),
  streamChatMock: vi.fn(),
}))

vi.mock('@/lib/api/client', () => ({
  getMatches: getMatchesMock,
  getPlayers: getPlayersMock,
  getMatch: getMatchMock,
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

function mockStream(options: {
  data?: StructuredData
  text?: string
  errorCode?: string
  errorDetails?: Record<string, unknown>
}) {
  streamChatMock.mockImplementation(() => {
    async function* generate(): AsyncGenerator<ChatEvent> {
      yield { type: 'status', payload: { stage: 'resolving' } }
      if (options.data) yield { type: 'data', payload: options.data }
      if (options.text) yield { type: 'text_delta', payload: { delta: options.text } }
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

beforeEach(() => {
  vi.clearAllMocks()
  Element.prototype.scrollIntoView = vi.fn()
  getMatchesMock.mockImplementation(async (status: string) => {
    if (status === 'live') return [liveDto]
    if (status === 'upcoming') return [upcomingDto]
    return []
  })
  mockStream({ data: { kind: 'matches', matches: [upcomingDto] }, text: 'Sinner 今晚 20:30 出场。' })
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
  it('loads live and upcoming exactly once without polling timers', async () => {
    render(<HomePage />)

    await screen.findByText('Jannik Sinner')
    await waitFor(() => {
      expect(getMatchesMock).toHaveBeenCalledWith('live')
      expect(getMatchesMock).toHaveBeenCalledWith('upcoming')
    })
    expect(getMatchesMock).toHaveBeenCalledTimes(2)

    // No polling: the call count stays stable over time without user action.
    await new Promise((resolve) => setTimeout(resolve, 150))
    expect(getMatchesMock).toHaveBeenCalledTimes(2)
  })

  it('refresh makes exactly one new pair of calls', async () => {
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    await userEvent.click(screen.getByRole('button', { name: '刷新比赛数据' }))

    await waitFor(() => {
      expect(getMatchesMock).toHaveBeenCalledTimes(4)
    })
  })

  it('keeps section shells with factual empty copy when lists are empty', async () => {
    getMatchesMock.mockResolvedValue([])

    render(<HomePage />)

    expect(await screen.findByText('暂无直播比赛')).toBeVisible()
    expect(screen.getByText('今晚暂无待开赛比赛')).toBeVisible()
    expect(screen.getByRole('heading', { name: '正在直播' })).toBeVisible()
    expect(screen.getByRole('heading', { name: '今晚比赛' })).toBeVisible()
  })

  it('renders typed retry copy when the slate API fails', async () => {
    getMatchesMock.mockRejectedValue(Object.assign(new Error('down'), { code: 'provider_unavailable' }))

    render(<HomePage />)

    expect(await screen.findByText(/provider_unavailable/)).toBeVisible()
    const retry = screen.getByRole('button', { name: '重试加载比赛数据' })
    expect(retry).toBeVisible()
  })

  it('keeps the healthy upcoming section when live loading fails', async () => {
    getMatchesMock.mockImplementation(async (status: string) => {
      if (status === 'live') {
        throw Object.assign(new Error('live down'), { code: 'provider_unavailable' })
      }
      return [upcomingDto]
    })

    render(<HomePage />)

    expect(await screen.findByText(/直播比赛加载失败（provider_unavailable）/)).toBeVisible()
    expect(screen.getByRole('heading', { name: '今晚比赛' })).toBeVisible()
    expect(screen.getByText('Carlos Alcaraz')).toBeVisible()
    expect(screen.queryByText(/比赛数据加载失败（provider_unavailable）/)).toBeNull()
  })
})

describe('HomePage chat', () => {
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

  it('renders unsupported without a card for historical questions', async () => {
    mockStream({
      data: { kind: 'unsupported', matches: [] },
      text: 'P1 暂不支持历史比赛结果查询。',
    })
    render(<HomePage />)
    await screen.findByText('Jannik Sinner')

    await askQuestion('昨天 Sinner 赢了吗？')

    expect(await screen.findByText('P1 暂不支持历史比赛结果查询。')).toBeVisible()
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
    expect(screen.getByText('数据由 Tennix 服务提供 · 时间为澳门本地时间')).toBeVisible()
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
