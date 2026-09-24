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
  availability: 'available' | 'partial' | 'stale' | 'unavailable' = 'available',
  period = 'match',
  asOf = '2026-09-09T12:00:00Z',
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
    as_of: asOf,
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
    const catalog = [
      ['aces', 'ACE 球', 'count'],
      ['double_faults', '双误', 'count'],
      ['first_serve_percentage', '一发成功率', 'percent'],
      ['first_serve_points_won', '一发得分率', 'percent'],
      ['second_serve_points_won', '二发得分率', 'percent'],
      ['service_points_won', '发球得分率', 'percent'],
      ['service_games_won', '发球局胜率', 'percent'],
      ['break_points_saved', '破发点挽救率', 'percent'],
      ['break_points_converted', '破发点转化率', 'percent'],
      ['return_points_won', '接发得分率', 'percent'],
      ['first_return_points_won', '一发接发得分率', 'percent'],
      ['second_return_points_won', '二发接发得分率', 'percent'],
      ['return_games_won', '接发局胜率', 'percent'],
      ['winners', '制胜分', 'count'],
      ['unforced_errors', '非受迫性失误', 'count'],
      ['net_points_won', '上网得分率', 'percent'],
      ['total_points_won', '总得分', 'percent'],
      ['total_games_won', '总赢局', 'percent'],
      ['match_points_saved', '赛点挽救', 'count'],
      ['average_first_serve_speed', '一发平均速度', 'km/h'],
      ['average_second_serve_speed', '二发平均速度', 'km/h'],
      ['distance_covered', '跑动距离', 'm'],
    ] as const

    render(
      <MatchStatisticsCard
        statistics={catalog.map(([name, , unit], index) => ({
          ...stat(name, index + 1, index + 101),
          unit,
        }))}
        points={[]}
        players={players}
      />,
    )

    for (const [index, [, label, unit]] of catalog.entries()) {
      const leftValue = index + 1
      const formatted = unit === 'percent'
        ? `${leftValue}%`
        : unit === 'count'
          ? String(leftValue)
          : `${leftValue} ${unit}`
      expect(screen.getByText(`全场 · ${label}`)).toBeVisible()
      expect(screen.getByText(formatted)).toBeVisible()
    }
    expect(screen.getByText('发球')).toBeVisible()
    expect(screen.getByText('接发')).toBeVisible()
    expect(screen.getByText('关键分')).toBeVisible()
    expect(screen.getByText('制胜与失误')).toBeVisible()
    expect(screen.getByText('总计')).toBeVisible()
    expect(screen.getByText('体能')).toBeVisible()
  })

  it('uses the canonical unit for total points and games won', () => {
    render(
      <MatchStatisticsCard
        statistics={[
          { ...stat('total_points_won', 49, 51), unit: 'percent' },
          { ...stat('total_games_won', 53, 47), unit: 'percent' },
        ]}
        points={[]}
        players={players}
      />,
    )

    expect(screen.getByText('49%')).toBeVisible()
    expect(screen.getByText('51%')).toBeVisible()
    expect(screen.getByText('53%')).toBeVisible()
    expect(screen.getByText('47%')).toBeVisible()
  })

  it('marks missing statistics as unavailable instead of zero', () => {
    render(
      <MatchStatisticsCard
        statistics={[stat('aces', 8, 5)]}
        points={[]}
        players={players}
      />,
    )

    expect(screen.getByText('双误官方未返回')).toBeVisible()
    expect(screen.queryByText('双误 0')).not.toBeInTheDocument()
    expect(screen.queryAllByText('0').length).toBe(0)
  })

  it('shows a single unavailable summary when no statistics exist', () => {
    render(<MatchStatisticsCard statistics={[]} points={[]} players={players} />)

    expect(screen.getByText(/供应商尚未返回本场技术统计/)).toBeVisible()
  })

  it('badges partial statistics', () => {
    render(
      <MatchStatisticsCard
        statistics={[stat('winners', 12, null, 'partial')]}
        points={[]}
        players={players}
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
      />,
    )

    const strip = screen.getByLabelText('最近 10 分')
    // Two of the last twelve points are indeterminate and excluded.
    expect(strip.querySelectorAll('li')).toHaveLength(10)
  })

  it('marks retained values stale and shows the newest statistic observation time', () => {
    render(
      <MatchStatisticsCard
        statistics={[
          stat('aces', 8, 5, 'stale', 'match', '2026-09-09T10:00:00Z'),
          stat('double_faults', 1, 3, 'available', 'match', '2026-09-09T11:00:00Z'),
        ]}
        points={[]}
        players={players}
      />,
    )

    expect(screen.getByText('数据较旧 · 9月9日 18:00')).toBeVisible()
    expect(screen.getByText(/最近统计观测：.*19:00；各项时间可能不同/)).toBeVisible()
  })
})
