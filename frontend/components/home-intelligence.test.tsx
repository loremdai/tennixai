// T68 Home Market Pulse production tests: zero-through-five candidates,
// urgent position reservation, cap at three, internal match links, the
// /markets link, absence of trajectories and ledger detail, honest
// disabled/empty/error states, and the stale overlay banner.
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { LiveMarketPulse } from '@/components/home/live-market-pulse'
import type { PulseRowDto } from '@/lib/api/types'

const { getMarketPulseMock } = vi.hoisted(() => ({
  getMarketPulseMock: vi.fn(),
}))

vi.mock('@/lib/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api/client')>()
  return { ...actual, getMarketPulse: getMarketPulseMock }
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

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

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
    as_of: new Date().toISOString(),
    ...overrides,
  }
}

beforeEach(() => {
  getMarketPulseMock.mockResolvedValue({ data: [], has_open_position: false })
})

describe('LiveMarketPulse', () => {
  it('renders zero candidates as the honest empty state', async () => {
    render(<LiveMarketPulse />)
    await waitFor(() =>
      expect(screen.getByText('暂无值得关注的市场机会')).toBeTruthy(),
    )
    expect(screen.queryAllByRole('link', { name: /查看 .*判断/ })).toHaveLength(0)
    // The /markets entry link stays available.
    expect(screen.getByRole('link', { name: /查看全部/ })).toHaveAttribute(
      'href',
      '/markets',
    )
  })

  it('reserves the urgent position row and caps five candidates at three', async () => {
    getMarketPulseMock.mockResolvedValue({
      data: [
        pulseRow({ match_id: 'mat_b1', action: 'buy', phase: 'live' }),
        pulseRow({
          match_id: 'mat_p1',
          kind: 'position',
          action: 'hold',
          conservative_net_edge: null,
          player_names: ['Position One', 'Position Two'],
        }),
        pulseRow({
          match_id: 'mat_b2',
          action: 'buy',
          phase: 'upcoming',
          player_names: ['Upcoming One', 'Upcoming Two'],
        }),
        pulseRow({
          match_id: 'mat_w1',
          action: 'wait',
          conservative_net_edge: null,
          player_names: ['Wait One', 'Wait Two'],
        }),
        pulseRow({
          match_id: 'mat_b3',
          action: 'buy',
          phase: 'live',
          player_names: ['Live Three', 'Live Four'],
        }),
      ],
      has_open_position: true,
    })
    render(<LiveMarketPulse />)

    await waitFor(() =>
      expect(screen.getAllByRole('link', { name: /查看 .*判断/ })).toHaveLength(3),
    )
    const rows = screen.getAllByRole('link', { name: /查看 .*判断/ })
    // Reserved position row first, then the two live BUYs in server order.
    expect(rows[0].getAttribute('aria-label')).toContain('Position One vs. Position Two')
    expect(rows[1].getAttribute('aria-label')).toContain('Alpha One vs. Beta Two')
    expect(rows[2].getAttribute('aria-label')).toContain('Live Three vs. Live Four')
    for (const row of rows) {
      expect(row.getAttribute('href')).toMatch(/^\/matches\//)
    }
  })

  it('reports availability and renders server values with internal links', async () => {
    getMarketPulseMock.mockResolvedValue({
      data: [pulseRow()],
      has_open_position: false,
    })
    const onAvailability = vi.fn()
    render(<LiveMarketPulse onAvailability={onAvailability} />)

    await waitFor(() => expect(screen.getByText('Alpha One vs. Beta Two')).toBeTruthy())
    expect(onAvailability).toHaveBeenCalledWith(true)
    expect(screen.getByText('62.0%')).toBeTruthy()
    expect(screen.getByText('55.0%')).toBeTruthy()
    expect(screen.getByText('+7.0 个百分点')).toBeTruthy()
    expect(screen.getByText('模拟买入机会')).toBeTruthy()
    expect(screen.getByRole('link', { name: /查看 .*判断/ })).toHaveAttribute(
      'href',
      '/matches/mat_1',
    )
  })

  it('renders no trajectories and no ledger detail', async () => {
    getMarketPulseMock.mockResolvedValue({
      data: [pulseRow({ kind: 'position', action: 'hold' })],
      has_open_position: true,
    })
    const { container } = render(<LiveMarketPulse />)

    await waitFor(() => expect(screen.getByText('模拟持有中')).toBeTruthy())
    expect(container.querySelector('.recharts-surface')).toBeNull()
    expect(screen.queryByText(/入场成本|份额|净 P&L/)).toBeNull()
  })

  it('shows the stale banner and keeps last trusted numbers', async () => {
    getMarketPulseMock.mockResolvedValue({
      data: [
        pulseRow({
          kind: 'position',
          action: 'hold',
          is_stale: true,
          as_of: new Date(Date.now() - 128_000).toISOString(),
        }),
      ],
      has_open_position: true,
    })
    render(<LiveMarketPulse />)

    await waitFor(() =>
      expect(
        screen.getByText(/部分市场报价更新较慢，已暂停相关模拟操作；仍显示上次有效报价/),
      ).toBeTruthy(),
    )
    expect(screen.getAllByText(/上次有效报价 ·/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('62.0%')).toBeTruthy()
  })

  it('renders nothing and reports unavailable on typed p3_disabled', async () => {
    const { ApiError } = await import('@/lib/api/client')
    getMarketPulseMock.mockRejectedValue(new ApiError(503, 'p3_disabled', 'disabled'))
    const onAvailability = vi.fn()
    const { container } = render(<LiveMarketPulse onAvailability={onAvailability} />)

    await waitFor(() => expect(onAvailability).toHaveBeenCalledWith(false))
    expect(container.innerHTML).toBe('')
  })

  it('shows an honest typed error with retry on transport failure', async () => {
    const { ApiError } = await import('@/lib/api/client')
    getMarketPulseMock.mockRejectedValue(new ApiError(502, 'internal_error', 'boom'))
    const user = userEvent.setup()
    render(<LiveMarketPulse />)

    await waitFor(() => expect(screen.getByRole('alert')).toBeTruthy())
    expect(screen.getByText('市场数据暂时无法加载，请稍后重试。')).toBeTruthy()
    expect(screen.queryByText(/internal_error/)).toBeNull()

    getMarketPulseMock.mockResolvedValue({ data: [pulseRow()], has_open_position: false })
    await user.click(screen.getByRole('button', { name: '重试' }))
    await waitFor(() => expect(screen.getByText('Alpha One vs. Beta Two')).toBeTruthy())
  })
})
