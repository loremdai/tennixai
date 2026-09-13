import { describe, expect, it } from 'vitest'

import type { PlayerHistoryContextDto, PlayerSeasonRecordDto } from '@/lib/api/types'
import {
  HISTORY_EMPTY_RESULTS_COPY,
  HISTORY_SEASON_UNAVAILABLE_COPY,
  historyEmptyCopy,
  historyPlayerHeading,
  historyScopeLabel,
  playerHistoryTitle,
  seasonSurfaceEntries,
  seasonWinRate,
} from './player-history-view'

const player = {
  id: 'ply_s',
  name: 'Jannik Sinner',
  country_code: 'ita',
  ranking: 1,
  localized_name: '辛纳',
}

function context(
  overrides: Partial<PlayerHistoryContextDto> = {},
): PlayerHistoryContextDto {
  return {
    player,
    scope: 'recent',
    season: null,
    availability: 'available',
    season_record: null,
    empty_reason: null,
    ...overrides,
  }
}

function record(overrides: Partial<PlayerSeasonRecordDto> = {}): PlayerSeasonRecordDto {
  return {
    season: 2026,
    matches_won: 30,
    matches_lost: 5,
    titles: 4,
    hard: { won: 20, lost: 3 },
    clay: null,
    grass: { won: 10, lost: 2 },
    ...overrides,
  }
}

describe('historyScopeLabel', () => {
  it('maps every approved scope to its label', () => {
    expect(historyScopeLabel(context({ scope: 'yesterday' }))).toBe('昨日赛果')
    expect(historyScopeLabel(context({ scope: 'last' }))).toBe('上一场比赛')
    expect(historyScopeLabel(context({ scope: 'recent' }))).toBe('近期赛果')
    expect(historyScopeLabel(context({ scope: 'season', season: 2026 }))).toBe('2026 赛季战绩')
  })
})

describe('historyPlayerHeading', () => {
  it('uses English primary with Chinese secondary', () => {
    expect(historyPlayerHeading(context())).toBe('Jannik Sinner（辛纳）')
  })

  it('falls back to English when no localized name exists', () => {
    expect(
      historyPlayerHeading(context({ player: { ...player, localized_name: null } })),
    ).toBe('Jannik Sinner')
  })
})

describe('playerHistoryTitle', () => {
  it('combines the player heading and the scope label', () => {
    expect(
      playerHistoryTitle({
        kind: 'player_history',
        matches: [],
        player_history: context({ scope: 'last' }),
      }),
    ).toBe('Jannik Sinner（辛纳） · 上一场比赛')
  })
})

describe('historyEmptyCopy', () => {
  it('keeps the two approved empty copies distinct', () => {
    expect(historyEmptyCopy(context({ scope: 'recent' }))).toBe(HISTORY_EMPTY_RESULTS_COPY)
    expect(historyEmptyCopy(context({ scope: 'season' }))).toBe(HISTORY_SEASON_UNAVAILABLE_COPY)
    expect(HISTORY_EMPTY_RESULTS_COPY).toBe('该范围暂无赛果信息')
    expect(HISTORY_SEASON_UNAVAILABLE_COPY).toBe('该赛季战绩暂不可用')
  })
})

describe('seasonWinRate', () => {
  it('computes the rounded rate from supplied wins and losses', () => {
    expect(seasonWinRate(record())).toBe('86%')
    expect(seasonWinRate(record({ matches_won: 0, matches_lost: 2 }))).toBe('0%')
  })

  it('stays unknown for a zero-match denominator', () => {
    expect(seasonWinRate(record({ matches_won: 0, matches_lost: 0 }))).toBeNull()
  })
})

describe('seasonSurfaceEntries', () => {
  it('returns only the available surfaces in a fixed order', () => {
    expect(seasonSurfaceEntries(record())).toEqual([
      { label: '硬地', text: '20-3' },
      { label: '草地', text: '10-2' },
    ])
    expect(seasonSurfaceEntries(record({ hard: null, grass: null }))).toEqual([])
  })
})
