import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'

import { MatchPointsTimeline } from './match-points'
import type { PlayerDto, PointEventDto } from '@/lib/api/types'

const players: [PlayerDto, PlayerDto] = [
  { id: 'ply_a', name: 'Jannik Sinner', country_code: 'ita', ranking: 1 },
  { id: 'ply_b', name: 'Carlos Alcaraz', country_code: 'esp', ranking: 2 },
]

function point(
  sequence: number,
  setNumber: number,
  gameNumber: number,
  options: {
    winner?: 'ply_a' | 'ply_b' | null
    score?: [string, string]
    breakPoint?: boolean
    setPoint?: boolean
    matchPoint?: boolean
    revision?: number
  } = {},
): PointEventDto {
  return {
    id: `pe_${setNumber}_${gameNumber}_${sequence}`,
    match_id: 'mat_1',
    sequence,
    set_number: setNumber,
    game_number: gameNumber,
    point_number: sequence,
    server_player_id: 'ply_a',
    winner_player_id: options.winner ?? 'ply_a',
    score_before: null,
    score_after: {
      sets_won: [0, 0],
      sets: [],
      points: options.score ?? ['15', '0'],
      is_tiebreak: false,
    },
    is_break_point: options.breakPoint ?? false,
    is_set_point: options.setPoint ?? false,
    is_match_point: options.matchPoint ?? false,
    observed_at: '2026-09-09T12:00:00Z',
    provider: 'fake',
    source_fingerprint: `fp-${sequence}`,
    revision: options.revision ?? 1,
    quality: null,
  }
}

const history: PointEventDto[] = [
  point(1, 1, 1, { score: ['15', '0'] }),
  point(2, 1, 1, { score: ['30', '0'] }),
  point(3, 1, 2, { score: ['0', '15'], winner: 'ply_b' }),
  point(4, 2, 1, { score: ['15', '0'] }),
  point(5, 2, 2, { score: ['30', '0'], breakPoint: true }),
  point(6, 2, 2, { score: ['40', '0'], setPoint: true }),
]

function makeScrollable(container: HTMLElement) {
  Object.defineProperty(container, 'scrollHeight', { configurable: true, value: 400 })
  Object.defineProperty(container, 'clientHeight', { configurable: true, value: 200 })
  Object.defineProperty(container, 'scrollTop', { configurable: true, writable: true, value: 190 })
}

afterEach(cleanup)

describe('MatchPointsTimeline', () => {
  it('groups points by set and game with key point badges', () => {
    render(<MatchPointsTimeline points={history} players={players} />)

    expect(screen.getByRole('button', { name: /第 1 盘/ })).toBeVisible()
    expect(screen.getByRole('button', { name: /第 2 盘/ })).toBeVisible()
    expect(screen.getAllByText('破发点').length).toBeGreaterThan(0)
    expect(screen.getAllByText('盘点').length).toBeGreaterThan(0)
    expect(screen.queryByText('赛点')).not.toBeInTheDocument()
  })

  it('expands the current set and game while collapsing older ones', () => {
    render(<MatchPointsTimeline points={history} players={players} />)

    const set1 = screen.getByRole('button', { name: /第 1 盘/ })
    const set2 = screen.getByRole('button', { name: /第 2 盘/ })
    expect(set1).toHaveAttribute('aria-expanded', 'false')
    expect(set2).toHaveAttribute('aria-expanded', 'true')
  })

  it('shows a non-intrusive correction notice when revisions exist', () => {
    render(
      <MatchPointsTimeline
        points={[...history, point(7, 2, 2, { score: ['40', '15'], revision: 2 })]}
        players={players}
      />,
    )

    expect(screen.getByRole('status', { name: /数据已校准/ })).toBeVisible()
  })

  it('does not show the correction notice without revisions', () => {
    render(<MatchPointsTimeline points={history} players={players} />)
    expect(screen.queryByRole('status', { name: /数据已校准/ })).not.toBeInTheDocument()
  })

  it('auto-follows new points only when the viewer is near the bottom', async () => {
    const { container, rerender } = render(
      <MatchPointsTimeline points={history} players={players} />,
    )
    const scroller = container.querySelector('[data-points-scroller]') as HTMLElement
    makeScrollable(scroller)

    rerender(<MatchPointsTimeline points={[...history, point(7, 2, 3)]} players={players} />)
    expect(scroller.scrollTop).toBe(400)

    // Viewer scrolled up: no auto scroll, but a new-point notice appears.
    scroller.scrollTop = 0
    scroller.dispatchEvent(new Event('scroll'))
    rerender(
      <MatchPointsTimeline
        points={[...history, point(7, 2, 3), point(8, 2, 3)]}
        players={players}
      />,
    )
    expect(scroller.scrollTop).toBe(0)
    const notice = screen.getByRole('button', { name: /有新分/ })
    expect(notice).toBeVisible()

    await userEvent.click(notice)
    expect(scroller.scrollTop).toBe(400)
  })

  it('renders an empty state without points', () => {
    render(<MatchPointsTimeline points={[]} players={players} />)
    expect(screen.getByText(/供应商尚未返回逐分数据/)).toBeVisible()
  })
})
