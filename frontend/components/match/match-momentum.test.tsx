import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { MatchDto, MatchSnapshotDto, PointEventDto } from '@/lib/api/types'
import type { MatchViewModel } from '@/lib/view-models'

import { MatchMomentumCard } from './match-momentum'

const matchDto: MatchDto = {
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
    score: null,
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

const match = {
  id: 'mat_1',
  canonicalStatus: 'live',
  visualStatus: 'live',
  tournament: 'ATP Finals',
  round: 'Semifinal',
  surface: '室内硬地',
  scheduledDate: '9月8日',
  scheduledTime: '18:00',
  timezoneLabel: '澳门时间',
  format: '三盘两胜 · BO3',
  indoorLabel: '室内',
  players: [
    { id: 'ply_1', name: 'Jannik Sinner', shortName: 'Sinner', initials: 'JS', countryCode: 'ITA', ranking: 1 },
    { id: 'ply_2', name: 'Carlos Alcaraz', shortName: 'Alcaraz', initials: 'CA', countryCode: 'ESP', ranking: 2 },
  ],
  score: null,
  serverPlayerId: 'ply_1',
  winnerPlayerId: null,
  freshnessLabel: '更新于 18:00',
  isStale: false,
} satisfies MatchViewModel

function point(sequence: number, options: Partial<PointEventDto> = {}): PointEventDto {
  return {
    id: `pe_${sequence}`,
    match_id: 'mat_1',
    sequence,
    set_number: 1,
    game_number: 1,
    point_number: sequence,
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
    source_fingerprint: `fp-${sequence}`,
    revision: 1,
    quality: null,
    ...options,
  }
}

function snapshot(momentumCount: number): MatchSnapshotDto {
  return {
    match: matchDto,
    points: Array.from({ length: momentumCount }, (_, index) => point(index + 1)),
    statistics: [],
    momentum: Array.from({ length: momentumCount }, (_, index) => ({
      match_id: 'mat_1',
      point_sequence: index + 1,
      state_version: 4,
      algorithm_version: 'recent-control-v1',
      value: index === momentumCount - 1 ? 16 : index - 4,
      leader_player_id: 'ply_1',
      is_provisional: momentumCount < 6,
      as_of: '2026-09-08T10:00:00Z',
      input_summary: `n=${index + 1}`,
    })),
    quality: [],
    state_version: 4,
    as_of: '2026-09-08T10:00:00Z',
  }
}

afterEach(cleanup)

describe('MatchMomentumCard', () => {
  it('renders the latest twenty observations, leader, as_of, and key-point markers', () => {
    const current = snapshot(22)
    current.points[21] = point(22, { is_break_point: true })

    render(
      <MatchMomentumCard
        match={match}
        preview={false}
        highlight={null}
        snapshot={current}
      />,
    )

    expect(screen.getByText('Sinner +16')).toBeVisible()
    expect(screen.getByText('最近 20 分的比赛控制指数')).toBeVisible()
    expect(screen.getByText(/更新于 9月8日 18:00/)).toBeVisible()
    expect(screen.getByText('关键分标记')).toBeVisible()
    expect(screen.getAllByText(/第 22 分/).length).toBeGreaterThan(0)
    expect(screen.getByRole('list', { name: '近期控制指数观测' }).querySelectorAll('li')).toHaveLength(20)
  })

  it('labels a short sample as provisional and stays honest when no index exists', () => {
    render(
      <MatchMomentumCard
        match={match}
        preview={false}
        highlight={null}
        snapshot={snapshot(5)}
      />,
    )
    expect(screen.getByText(/样本较少/)).toBeVisible()

    cleanup()
    render(
      <MatchMomentumCard
        match={match}
        preview={false}
        highlight={null}
        snapshot={{ ...snapshot(0), points: [] }}
      />,
    )
    expect(screen.getByText(/近期控制指数暂未提供/)).toBeVisible()
  })
})
