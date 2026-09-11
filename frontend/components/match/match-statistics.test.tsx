import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { MatchStatisticsCard } from './match-statistics'
import type { MatchStatisticDto, PlayerDto, PointEventDto } from '@/lib/api/types'

const players: [PlayerDto, PlayerDto] = [
  { id: 'ply_a', name: 'Jannik Sinner', country_code: 'ita', ranking: 1 },
  { id: 'ply_b', name: 'Carlos Alcaraz', country_code: 'esp', ranking: 2 },
]

function stat(
  name: string,
  p1: number | null,
  p2: number | null,
  availability: 'available' | 'partial' | 'unavailable' = 'available',
  period = 'match',
): MatchStatisticDto {
  return {
    match_id: 'mat_1',
    name,
    period,
    player1_value: p1,
    player2_value: p2,
    unit: null,
    provenance: 'provider',
    availability,
    as_of: '2026-09-09T12:00:00Z',
  }
}

function point(sequence: number, winner: 'ply_a' | 'ply_b' | null): PointEventDto {
  return {
    id: `pe_${sequence}`,
    match_id: 'mat_1',
    sequence,
    set_number: 1,
    game_number: 1,
    point_number: sequence,
    server_player_id: 'ply_a',
    winner_player_id: winner,
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
    observed_at: '2026-09-09T12:00:00Z',
    provider: 'fake',
    source_fingerprint: `fp-${sequence}`,
    revision: 1,
    quality: null,
  }
}

afterEach(cleanup)

describe('MatchStatisticsCard', () => {
  it('renders the 22 canonical labels with units and groups', () => {
    render(
      <MatchStatisticsCard
        statistics={[
          stat('aces', 8, 5),
          stat('double_faults', 1, 3),
          stat('first_serve_percentage', 68, 61),
          stat('average_first_serve_speed', 181, 176),
          stat('distance_covered', 2410, 2600),
        ]}
        points={[]}
        players={players}
        asOf="2026-09-09T12:00:00Z"
      />,
    )

    expect(screen.getByText('全场 · ACE 球')).toBeVisible()
    expect(screen.getByText('8')).toBeVisible()
    expect(screen.getByText('全场 · 双误')).toBeVisible()
    expect(screen.getByText('全场 · 一发成功率')).toBeVisible()
    expect(screen.getByText('68%')).toBeVisible()
    expect(screen.getByText('181 km/h')).toBeVisible()
    expect(screen.getByText('2410 m')).toBeVisible()
    expect(screen.getByText('发球')).toBeVisible()
    expect(screen.getByText('体能')).toBeVisible()
  })

  it('marks missing statistics as unavailable instead of zero', () => {
    render(
      <MatchStatisticsCard
        statistics={[stat('aces', 8, 5)]}
        points={[]}
        players={players}
        asOf="2026-09-09T12:00:00Z"
      />,
    )

    expect(screen.getByText('双误官方未返回')).toBeVisible()
    expect(screen.queryByText('双误 0')).not.toBeInTheDocument()
    expect(screen.queryAllByText('0').length).toBe(0)
  })

  it('shows a single unavailable summary when no statistics exist', () => {
    render(
      <MatchStatisticsCard statistics={[]} points={[]} players={players} asOf={null} />,
    )

    expect(screen.getByText(/供应商尚未返回本场技术统计/)).toBeVisible()
  })

  it('badges partial statistics', () => {
    render(
      <MatchStatisticsCard
        statistics={[stat('winners', 12, null, 'partial')]}
        points={[]}
        players={players}
        asOf="2026-09-09T12:00:00Z"
      />,
    )

    expect(screen.getByText('全场 · 制胜分')).toBeVisible()
    expect(screen.getByText('部分提供')).toBeVisible()
    expect(screen.getByText('官方未返回')).toBeVisible()
  })

  it('keeps same statistic rows distinct when provider reports multiple periods', () => {
    render(
      <MatchStatisticsCard
        statistics={[
          stat('aces', 8, 5, 'available', 'match'),
          stat('aces', 4, 2, 'available', 'set:1'),
        ]}
        points={[]}
        players={players}
        asOf="2026-09-09T12:00:00Z"
      />,
    )

    expect(screen.getByText('全场 · ACE 球')).toBeVisible()
    expect(screen.getByText('第 1 盘 · ACE 球')).toBeVisible()
  })

  it('derives the last ten points from determinate point events only', () => {
    const points = [
      ...Array.from({ length: 12 }, (_, index) => point(index + 1, index < 2 ? null : 'ply_a')),
    ]
    render(
      <MatchStatisticsCard
        statistics={[stat('aces', 1, 1)]}
        points={points}
        players={players}
        asOf="2026-09-09T12:00:00Z"
      />,
    )

    const strip = screen.getByLabelText('最近 10 分')
    // Two of the last twelve points are indeterminate and excluded.
    expect(strip.querySelectorAll('li')).toHaveLength(10)
  })
})
