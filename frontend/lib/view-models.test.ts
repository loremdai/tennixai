import { describe, expect, it } from 'vitest'

import { formatAsOf, formatStatValue, STAT_META, toHomeMatch, toMatchViewModel } from './view-models'
import type { MatchDto } from '@/lib/api/types'

function baseMatch(overrides: Partial<MatchDto> = {}): MatchDto {
  return {
    id: 'mat_abc123',
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
      provider: 'livetennis',
      source_updated_at: null,
      observed_at: '2026-09-08T10:00:00Z',
      is_stale: false,
      age_seconds: 0,
    },
    ...overrides,
  }
}

function liveMatch(overrides: Partial<MatchDto> = {}): MatchDto {
  return baseMatch({
    status: 'live',
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
    ...overrides,
  })
}

describe('toHomeMatch', () => {
  it('maps an upcoming match with internal href and Macau time', () => {
    const view = toHomeMatch(baseMatch())

    expect(view.id).toBe('mat_abc123')
    expect(view.href).toBe('/matches/mat_abc123')
    expect(view.status).toBe('upcoming')
    expect(view.tournament).toBe('ATP Finals')
    expect(view.round).toBe('Semifinal')
    expect(view.surface).toBe('室内硬地')
    expect(view.time).toBe('20:30')
    expect(view.players).toEqual(['Sinner', 'Alcaraz'])
    expect(view.isStale).toBe(false)
    expect(view.score).toBeUndefined()
  })

  it('maps a live match score rows with serving flags', () => {
    const view = toHomeMatch(liveMatch())

    expect(view.status).toBe('live')
    expect(view.score).toBeDefined()
    expect(view.score?.rows[0]).toEqual({
      player: 'Sinner',
      sets: ['6', '4', '4'],
      points: '30',
      serving: true,
    })
    expect(view.score?.rows[1]).toEqual({
      player: 'Alcaraz',
      sets: ['4', '6', '5'],
      points: '15',
      serving: false,
    })
  })

  it('renders unavailable copy for null fields', () => {
    const view = toHomeMatch(
      baseMatch({ round: null, surface: null, indoor: null, scheduled_at: null }),
    )

    expect(view.round).toBe('暂未提供')
    expect(view.surface).toBe('暂未提供')
    expect(view.time).toBe('暂未提供')
  })

  it('maps cancelled, postponed, and unknown to unavailable status', () => {
    expect(toHomeMatch(baseMatch({ status: 'cancelled' })).status).toBe('unavailable')
    expect(toHomeMatch(baseMatch({ status: 'postponed' })).status).toBe('unavailable')
    expect(toHomeMatch(baseMatch({ status: 'unknown' })).status).toBe('unavailable')
    expect(toHomeMatch(baseMatch({ status: 'finished' })).status).toBe('finished')
  })

  it('marks stale data with a visible freshness label', () => {
    const stale = toHomeMatch(
      liveMatch({
        freshness: {
          provider: 'livetennis',
          source_updated_at: null,
          observed_at: '2026-09-08T10:00:00Z',
          is_stale: true,
          age_seconds: 240,
        },
      }),
    )

    expect(stale.isStale).toBe(true)
    expect(stale.freshnessLabel).toContain('数据较旧')
    expect(stale.freshnessLabel).toContain('240')
  })
})

describe('toMatchViewModel', () => {
  it('maps canonical and visual status separately', () => {
    const view = toMatchViewModel(baseMatch())

    expect(view.canonicalStatus).toBe('scheduled')
    expect(view.visualStatus).toBe('upcoming')
    expect(view.timezoneLabel).toBe('澳门时间')
    expect(view.scheduledTime).toBe('20:30')
    expect(view.scheduledDate).toContain('9')
    expect(view.scheduledDate).toContain('8')
  })

  it('maps player presentation fields without flag URLs', () => {
    const view = toMatchViewModel(baseMatch())

    expect(view.players[0]).toEqual({
      id: 'ply_1',
      name: 'Jannik Sinner',
      shortName: 'Sinner',
      initials: 'JS',
      countryCode: 'ITA',
      ranking: 1,
    })
    expect(JSON.stringify(view)).not.toContain('flagUrl')
  })

  it('maps meta fields with unavailable fallbacks', () => {
    const view = toMatchViewModel(
      baseMatch({ round: null, surface: null, indoor: null, format: null, scheduled_at: null }),
    )

    expect(view.round).toBe('暂未提供')
    expect(view.surface).toBe('暂未提供')
    expect(view.indoorLabel).toBe('暂未提供')
    expect(view.format).toBe('暂未提供')
    expect(view.scheduledDate).toBe('暂未提供')
    expect(view.scheduledTime).toBe('暂未提供')
  })

  it('maps format and indoor labels', () => {
    expect(toMatchViewModel(baseMatch({ format: 'BO3' })).format).toContain('BO3')
    expect(toMatchViewModel(baseMatch({ format: 'BO5' })).format).toContain('BO5')
    expect(toMatchViewModel(baseMatch({ indoor: true })).indoorLabel).toBe('室内')
    expect(toMatchViewModel(baseMatch({ indoor: false })).indoorLabel).toBe('室外')
  })

  it('carries score, server, and winner ids unchanged', () => {
    const view = toMatchViewModel(
      liveMatch({ status: 'finished', winner_player_id: 'ply_2' }),
    )

    expect(view.score?.points).toEqual(['30', '15'])
    expect(view.serverPlayerId).toBe('ply_1')
    expect(view.winnerPlayerId).toBe('ply_2')
    expect(view.visualStatus).toBe('finished')
  })

  it('exposes surface labels in Chinese', () => {
    expect(toMatchViewModel(baseMatch({ surface: 'hard', indoor: true })).surface).toBe('室内硬地')
    expect(toMatchViewModel(baseMatch({ surface: 'hard', indoor: false })).surface).toBe('硬地')
    expect(toMatchViewModel(baseMatch({ surface: 'clay', indoor: false })).surface).toBe('红土')
    expect(toMatchViewModel(baseMatch({ surface: 'grass', indoor: false })).surface).toBe('草地')
  })
})

describe('statistics presentation mapping', () => {
  it('covers all 22 canonical statistic names with labels, units and groups', () => {
    const names = [
      'aces', 'double_faults', 'first_serve_percentage', 'first_serve_points_won',
      'second_serve_points_won', 'service_points_won', 'service_games_won',
      'break_points_saved', 'break_points_converted', 'return_points_won',
      'first_return_points_won', 'second_return_points_won', 'return_games_won',
      'winners', 'unforced_errors', 'net_points_won', 'total_points_won',
      'total_games_won', 'match_points_saved', 'average_first_serve_speed',
      'average_second_serve_speed', 'distance_covered',
    ]
    expect(Object.keys(STAT_META)).toHaveLength(22)
    for (const name of names) {
      const meta = STAT_META[name]
      expect(meta, name).toBeDefined()
      expect(meta.label.length, name).toBeGreaterThan(0)
      expect(['count', 'percent', 'km/h', 'm'], name).toContain(meta.unit)
    }
    expect(STAT_META.aces.label).toBe('ACE 球')
    expect(STAT_META.double_faults.label).toBe('双误')
  })

  it('formats values by unit', () => {
    expect(formatStatValue(8, 'count')).toBe('8')
    expect(formatStatValue(68, 'percent')).toBe('68%')
    expect(formatStatValue(181.5, 'km/h')).toBe('181.5 km/h')
    expect(formatStatValue(2410, 'm')).toBe('2410 m')
    expect(formatStatValue(null, 'count')).toBe('暂未提供')
  })

  it('formats snapshot as_of in Macau time and keeps missing values null', () => {
    const label = formatAsOf('2026-09-08T10:00:00Z')
    expect(label).toMatch(/9月8日/)
    expect(label).toMatch(/18:00/)
    expect(formatAsOf(null)).toBeNull()
    expect(formatAsOf('not-a-date')).toBeNull()
  })
})
