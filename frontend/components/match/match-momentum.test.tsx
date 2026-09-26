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
  timezoneLabel: '北京时间',
  format: '三盘两胜 · BO3',
  indoorLabel: '室内',
  players: [
    { id: 'ply_1', name: 'Jannik Sinner', nameZh: '扬尼克·辛纳', shortName: 'Sinner', countryCode: 'ITA', countryName: '意大利', flagUrl: 'https://flagcdn.com/w40/it.png', ranking: 1 },
    { id: 'ply_2', name: 'Carlos Alcaraz', nameZh: '卡洛斯·阿尔卡拉斯', shortName: 'Alcaraz', countryCode: 'ESP', countryName: '西班牙', flagUrl: 'https://flagcdn.com/w40/es.png', ranking: 2 },
  ],
  score: null,
  currentSetNumber: null,
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
  it('shows a plain-language leader, both chart sides, and the latest twenty confirmed points', () => {
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

    const momentum = document.getElementById('momentum')
    expect(momentum).not.toBeNull()
    const conclusion = screen.getByRole('heading', { level: 3, name: /近期走势偏向/ })
    expect(conclusion).toHaveTextContent('Jannik Sinner')
    expect(conclusion).toHaveTextContent('扬尼克·辛纳')
    expect(screen.getByText('上方：').parentElement).toHaveTextContent('Sinner')
    expect(screen.getByText('下方：').parentElement).toHaveTextContent('Alcaraz')
    expect(screen.getByText('0 · 相对均衡')).toBeVisible()
    expect(screen.getByText('走势指数 +16（不是胜率）')).toBeVisible()
    expect(screen.getByText('最近 20 个已确认得分')).toBeVisible()
    expect(screen.getByText('查看近期得分走势与关键分')).toBeVisible()
    expect(screen.getByText(/走势截至 9月8日 18:00/)).toBeVisible()
    expect(screen.getByText('关键分标记')).toBeVisible()
    expect(screen.getAllByText(/第 22 分/).length).toBeGreaterThan(0)
    expect(screen.getByRole('list', { name: '近期比赛走势观测' }).querySelectorAll('li')).toHaveLength(20)
  })

  it('uses the signed index even when a negative observation has no leader id', () => {
    const current = snapshot(8)
    current.momentum[7] = { ...current.momentum[7], value: -14.6, leader_player_id: null }

    render(<MatchMomentumCard match={match} preview={false} highlight={null} snapshot={current} />)

    const conclusion = screen.getByRole('heading', { level: 3, name: /近期走势偏向/ })
    expect(conclusion).toHaveTextContent('Carlos Alcaraz')
    expect(conclusion).toHaveTextContent('卡洛斯·阿尔卡拉斯')
    expect(screen.getByText('走势指数 -14.6（不是胜率）')).toBeVisible()
  })

  it('calls zero balanced instead of guessing a leader', () => {
    const current = snapshot(8)
    current.momentum[7] = { ...current.momentum[7], value: 0, leader_player_id: null }

    render(<MatchMomentumCard match={match} preview={false} highlight={null} snapshot={current} />)

    expect(screen.getByRole('heading', { level: 3, name: '近期走势接近均衡' })).toBeVisible()
    expect(screen.getByText('走势指数 0（不是胜率）')).toBeVisible()
  })

  it('uses the displayed precision when deciding whether either side leads', () => {
    const current = snapshot(8)
    current.momentum[7] = { ...current.momentum[7], value: -0.04 }

    render(<MatchMomentumCard match={match} preview={false} highlight={null} snapshot={current} />)

    expect(screen.getByRole('heading', { level: 3, name: '近期走势接近均衡' })).toBeVisible()
    expect(screen.getByText('走势指数 0（不是胜率）')).toBeVisible()
  })

  it('uses full names to distinguish two players with the same surname', () => {
    const sameSurname = {
      ...match,
      players: [
        { ...match.players[0], name: 'Na Li', shortName: 'Li', nameZh: undefined },
        { ...match.players[1], name: 'Xian Li', shortName: 'Li', nameZh: undefined },
      ],
    } satisfies MatchViewModel

    render(<MatchMomentumCard match={sameSurname} preview={false} highlight={null} snapshot={snapshot(8)} />)

    expect(screen.getByText('上方：').parentElement).toHaveTextContent('Na Li')
    expect(screen.getByText('下方：').parentElement).toHaveTextContent('Xian Li')
  })

  it('discloses missing point winners without connecting the trend through them', () => {
    const current = snapshot(8)
    current.points[3] = point(4, { winner_player_id: null })
    current.momentum = current.momentum.filter((observation) => observation.point_sequence !== 4)

    render(<MatchMomentumCard match={match} preview={false} highlight={null} snapshot={current} />)

    expect(screen.getByText('有些得分未纳入走势，曲线在缺口处断开。')).toBeVisible()
    expect(screen.getByRole('list', { name: '近期比赛走势观测' }).querySelectorAll('li')).toHaveLength(7)
  })

  it('discloses newer points that cannot be represented by the trend', () => {
    const current = snapshot(8)
    current.points.push(point(9, { winner_player_id: null }))
    current.points.push(point(10, { winner_player_id: null }))

    render(<MatchMomentumCard match={match} preview={false} highlight={null} snapshot={current} />)

    expect(screen.getByText('之后还有 2 分得分者无法确认，走势停留在第 8 分。')).toBeVisible()

    cleanup()
    current.points[9] = point(10)
    render(<MatchMomentumCard match={match} preview={false} highlight={null} snapshot={current} />)
    expect(screen.getByText('之后还有 2 分尚未计入走势，走势停留在第 8 分。')).toBeVisible()
  })

  it('excludes a winner outside this match from the trend and its sample count', () => {
    const current = snapshot(8)
    current.points[7] = point(8, { winner_player_id: 'ply_other' })

    render(<MatchMomentumCard match={match} preview={false} highlight={null} snapshot={current} />)

    expect(screen.getByText('最近 7 个已确认得分')).toBeVisible()
    expect(screen.getByText('走势指数 +2（不是胜率）')).toBeVisible()
    expect(screen.getByText('之后还有 1 分得分者无法确认，走势停留在第 7 分。')).toBeVisible()
  })

  it('uses the latest momentum observation time instead of the snapshot time', () => {
    const current = snapshot(6)
    current.as_of = '2026-09-08T11:00:00Z'
    current.momentum.at(-1)!.as_of = '2026-09-08T10:00:00Z'

    render(
      <MatchMomentumCard
        match={match}
        preview={false}
        highlight={null}
        snapshot={current}
      />,
    )

    expect(screen.getByText(/走势截至 9月8日 18:00/)).toBeVisible()
    expect(screen.queryByText(/走势截至 9月8日 19:00/)).toBeNull()
  })

  it('labels a short sample clearly and explains when no trend data is available', () => {
    render(
      <MatchMomentumCard
        match={match}
        preview={false}
        highlight={null}
        snapshot={snapshot(5)}
      />,
    )
    expect(screen.getByText('样本较少')).toBeVisible()
    expect(screen.getByText('可确认得分不足，暂不判断走势。')).toBeVisible()
    expect(screen.queryByRole('heading', { level: 3, name: /近期走势偏向/ })).toBeNull()

    cleanup()
    const incomplete = snapshot(5)
    incomplete.momentum = incomplete.momentum.map((item) => ({ ...item, is_provisional: false }))
    render(<MatchMomentumCard match={match} preview={false} highlight={null} snapshot={incomplete} />)
    expect(screen.getByText('可确认得分不足，暂不判断走势。')).toBeVisible()
    expect(screen.queryByText('走势指数 +16（不是胜率）')).toBeNull()

    cleanup()
    render(
      <MatchMomentumCard
        match={match}
        preview={false}
        highlight={null}
        snapshot={{ ...snapshot(0), points: [] }}
      />,
    )
    expect(screen.getByText(/暂时没有可用的逐分记录/)).toBeVisible()

    cleanup()
    render(
      <MatchMomentumCard
        match={match}
        preview={false}
        highlight={null}
        snapshot={{ ...snapshot(0), points: [point(1, { winner_player_id: null })] }}
      />,
    )
    expect(screen.getByText('已有逐分记录，但得分者均无法确认，暂不能绘制走势。')).toBeVisible()

    cleanup()
    render(
      <MatchMomentumCard
        match={match}
        preview={false}
        highlight={null}
        snapshot={{ ...snapshot(0), points: [point(1)] }}
      />,
    )
    expect(screen.getByText('已有得分记录，走势尚未生成。')).toBeVisible()
  })
})
