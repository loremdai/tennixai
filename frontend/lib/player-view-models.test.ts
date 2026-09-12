import { describe, expect, it } from 'vitest'

import type {
  MatchDto,
  PlayerProfileViewDto,
  PlayerResultPageDto,
  PlayerSearchResolutionDto,
  PlayerSeasonRecordDto,
  RankingEntryDto,
} from '@/lib/api/types'
import {
  PRODUCTION_COUNTRY_OPTIONS,
  resultsHistoryState,
  searchResolutionToEntries,
  toCurrentStatus,
  toDirectoryEntry,
  toProfilePreview,
  toResultPreview,
  toSeasonSummary,
  viewTierToCircuitTier,
} from '@/lib/player-view-models'

const NOW = new Date('2026-09-08T10:00:00Z')

function rankingEntryFixture(overrides: Partial<RankingEntryDto> = {}): RankingEntryDto {
  return {
    player: {
      id: 'ply_zheng',
      name: 'Qinwen Zheng',
      localized_name: '郑钦文',
      country_code: 'chn',
      ranking: 5,
    },
    tour: 'WTA',
    rank: 5,
    points: 5315,
    movement: 'up',
    ranking_date: '2026-09-08',
    fetched_at: '2026-09-08T10:00:00Z',
    ...overrides,
  }
}

function matchFixture(overrides: Partial<MatchDto> = {}): MatchDto {
  return {
    id: 'mat_1',
    status: 'finished',
    players: [
      { id: 'ply_self', name: 'Ben Shelton', localized_name: '本·谢尔顿', country_code: 'usa', ranking: 9 },
      { id: 'ply_opp', name: 'Casper Ruud', localized_name: '卡斯珀·鲁德', country_code: 'nor', ranking: 12 },
    ],
    tournament: { id: 'trn_1', name: 'Fake ATP Event 1', tour: 'atp', circuit: 'atp' },
    scheduled_at: '2026-03-05T10:00:00Z',
    round: '1st Round',
    surface: 'hard',
    indoor: false,
    format: 'BO3',
    live_state: null,
    winner_player_id: 'ply_opp',
    freshness: {
      provider: 'fake',
      source_updated_at: null,
      observed_at: '2026-09-08T10:00:00Z',
      is_stale: false,
      age_seconds: 10,
    },
    ...overrides,
  }
}

function seasonRecordFixture(overrides: Partial<PlayerSeasonRecordDto> = {}): PlayerSeasonRecordDto {
  return {
    season: 2026,
    matches_won: 30,
    matches_lost: 10,
    titles: 2,
    hard: { won: 20, lost: 5 },
    clay: { won: 8, lost: 3 },
    grass: null,
    ...overrides,
  }
}

function profileViewFixture(overrides: Partial<PlayerProfileViewDto> = {}): PlayerProfileViewDto {
  return {
    profile: {
      player: {
        id: 'ply_self',
        name: 'Ben Shelton',
        localized_name: '本·谢尔顿',
        country_code: 'usa',
        ranking: 9,
      },
      birth_date: '2002-10-09',
      image_url: 'https://example.internal/ben.png',
      seasons: [seasonRecordFixture()],
    },
    selected_season: 2026,
    season_record: seasonRecordFixture(),
    current_match: null,
    ...overrides,
  }
}

describe('toDirectoryEntry', () => {
  it('maps an English-primary name with optional Chinese secondary name', () => {
    const entry = toDirectoryEntry(rankingEntryFixture())

    expect(entry).toMatchObject({
      id: 'ply_zheng',
      tour: 'WTA',
      name: 'Qinwen Zheng',
      nameZh: '郑钦文',
      countryCode: 'CHN',
      countryName: '中国',
      rank: 5,
      points: 5315,
      avatarUrl: null,
      aliases: [],
    })
    expect(entry.flagUrl).toContain('/cn.png')
  })

  it('keeps a missing localized name null instead of guessing', () => {
    const entry = toDirectoryEntry(
      rankingEntryFixture({
        player: { id: 'ply_x', name: 'Coleman Wong', localized_name: null, country_code: 'hkg', ranking: 201 },
        rank: 201,
      }),
    )

    expect(entry.nameZh).toBeNull()
    expect(entry.countryName).toBe('中国香港')
    expect(entry.rank).toBe(201)
  })

  it('maps movement labels without inventing place counts', () => {
    expect(toDirectoryEntry(rankingEntryFixture({ movement: 'up' })).movement).toEqual({ direction: 'up', places: null })
    expect(toDirectoryEntry(rankingEntryFixture({ movement: 'down' })).movement).toEqual({ direction: 'down', places: null })
    expect(toDirectoryEntry(rankingEntryFixture({ movement: 'same' })).movement).toEqual({ direction: 'flat', places: 0 })
    expect(toDirectoryEntry(rankingEntryFixture({ movement: 'unknown' })).movement).toEqual({ direction: 'unknown', places: null })
  })
})

describe('searchResolutionToEntries', () => {
  it('maps a resolved player with a null rank for 暂无当前排名 display', () => {
    const resolution: PlayerSearchResolutionDto = {
      status: 'resolved',
      query: 'Shelton',
      player: { id: 'ply_self', name: 'Ben Shelton', localized_name: null, country_code: 'usa', ranking: null },
      candidates: [],
    }

    const entries = searchResolutionToEntries(resolution)

    expect(entries).toHaveLength(1)
    expect(entries[0]).toMatchObject({ id: 'ply_self', name: 'Ben Shelton', tour: null, rank: null, points: null })
  })

  it('maps ambiguous candidates and prefers the directory current rank', () => {
    const resolution: PlayerSearchResolutionDto = {
      status: 'ambiguous',
      query: 'Wang',
      player: null,
      candidates: [
        {
          player: { id: 'ply_a', name: 'Xinyu Wang', localized_name: '王欣瑜', country_code: 'chn', ranking: null },
          matched_alias: 'wang',
          alias_kind: 'surname',
          current_rank: 25,
        },
        {
          player: { id: 'ply_b', name: 'Xiyu Wang', localized_name: '王曦雨', country_code: 'chn', ranking: 50 },
          matched_alias: 'wang',
          alias_kind: 'surname',
          current_rank: null,
        },
      ],
    }

    const entries = searchResolutionToEntries(resolution)

    expect(entries.map((entry) => entry.id)).toEqual(['ply_a', 'ply_b'])
    expect(entries[0].rank).toBe(25)
    expect(entries[1].rank).toBe(50)
  })

  it('maps not_found onto an empty list', () => {
    expect(
      searchResolutionToEntries({ status: 'not_found', query: '王', player: null, candidates: [] }),
    ).toEqual([])
  })
})

describe('toProfilePreview', () => {
  it('computes age from the birth date at the given instant', () => {
    const preview = toProfilePreview(profileViewFixture(), NOW)

    expect(preview).toMatchObject({
      id: 'ply_self',
      name: 'Ben Shelton',
      nameZh: '本·谢尔顿',
      countryCode: 'USA',
      countryName: '美国',
      rank: 9,
      points: null,
      tour: null,
      avatarUrl: 'https://example.internal/ben.png',
      birthDate: '2002-10-09',
      age: 23,
      rankUpdatedAt: null,
    })
  })

  it('keeps birth date and age unavailable without guessing', () => {
    const view = profileViewFixture()
    view.profile.birth_date = null

    const preview = toProfilePreview(view, NOW)

    expect(preview.birthDate).toBeNull()
    expect(preview.age).toBeNull()
  })
})

describe('toSeasonSummary', () => {
  it('maps wins, losses, win rate, titles and per-surface records', () => {
    expect(toSeasonSummary(2026, seasonRecordFixture())).toEqual({
      season: 2026,
      matches: 40,
      wins: 30,
      losses: 10,
      winRate: 75,
      titles: 2,
      hard: { won: 20, lost: 5 },
      clay: { won: 8, lost: 3 },
      grass: null,
    })
  })

  it('reports a null win rate for zero matches instead of dividing by zero', () => {
    const summary = toSeasonSummary(2026, seasonRecordFixture({ matches_won: 0, matches_lost: 0, titles: 0 }))

    expect(summary.matches).toBe(0)
    expect(summary.winRate).toBeNull()
  })

  it('maps a missing season record onto fully unavailable semantics', () => {
    expect(toSeasonSummary(2022, null)).toEqual({
      season: 2022,
      matches: null,
      wins: null,
      losses: null,
      winRate: null,
      titles: null,
      hard: null,
      clay: null,
      grass: null,
    })
  })
})

describe('toResultPreview', () => {
  it('maps a finished loss with the opponent and unavailable score', () => {
    const result = toResultPreview(matchFixture(), 'ply_self', 2026)

    expect(result).toMatchObject({
      id: 'mat_1',
      matchId: 'mat_1',
      season: 2026,
      date: '2026-03-05',
      tournament: 'Fake ATP Event 1',
      tournamentZh: null,
      tier: 'ATP',
      surface: '硬地',
      round: '1st Round',
      outcome: 'loss',
      score: null,
    })
    expect(result.opponent).toMatchObject({
      name: 'Casper Ruud',
      nameZh: '卡斯珀·鲁德',
      countryCode: 'NOR',
      countryName: '挪威',
    })
  })

  it('formats the score from the profiled player perspective', () => {
    const won = matchFixture({
      winner_player_id: 'ply_self',
      live_state: {
        score: {
          sets_won: [2, 0],
          sets: [
            { number: 1, player1_games: 6, player2_games: 4 },
            { number: 2, player1_games: 3, player2_games: 6 },
          ],
          points: [null, null],
          is_tiebreak: false,
        },
        server_player_id: null,
      },
    })

    expect(toResultPreview(won, 'ply_self', 2026).score).toBe('6–4 3–6')
    expect(toResultPreview(won, 'ply_opp', 2026).score).toBe('4–6 6–3')
    expect(toResultPreview(won, 'ply_opp', 2026).outcome).toBe('loss')
  })

  it('maps tier and surface values, keeping unknown ones truthful', () => {
    const challenger = matchFixture({
      tournament: { id: 'trn_c', name: 'Fake CH Event', tour: 'atp', circuit: 'challenger' },
      surface: 'carpet',
    })
    expect(toResultPreview(challenger, 'ply_self', 2026).tier).toBe('Challenger')
    expect(toResultPreview(challenger, 'ply_self', 2026).surface).toBe('carpet')

    const other = matchFixture({
      tournament: { id: 'trn_o', name: 'Fake Event', tour: null },
      surface: null,
      round: null,
      scheduled_at: null,
    })
    const mapped = toResultPreview(other, 'ply_self', 2026)
    expect(mapped.tier).toBe('Other')
    expect(mapped.surface).toBeNull()
    expect(mapped.round).toBeNull()
    expect(mapped.date).toBeNull()
    expect(mapped.season).toBe(2026)
  })
})

describe('toCurrentStatus', () => {
  it('renders the exact empty copy when no live or next match exists', () => {
    expect(toCurrentStatus(null, 'ply_self', NOW)).toEqual({
      kind: 'none',
      message: '当前没有可用的正在进行或即将开始的单打比赛。',
    })
  })

  it('maps a live match with score, server and freshness', () => {
    const live = matchFixture({
      status: 'live',
      live_state: {
        score: {
          sets_won: [1, 0],
          sets: [
            { number: 1, player1_games: 6, player2_games: 4 },
            { number: 2, player1_games: 3, player2_games: 2 },
          ],
          points: ['40', '30'],
          is_tiebreak: false,
        },
        server_player_id: 'ply_self',
      },
    })

    const status = toCurrentStatus(live, 'ply_self', NOW)

    expect(status).toMatchObject({
      kind: 'live',
      matchId: 'mat_1',
      event: 'Fake ATP Event 1',
      round: '1st Round',
      score: '6–4 3–2 · 40–30',
      detail: '当前由本球员发球',
      freshness: '刚刚更新',
    })
  })

  it('names the opponent server and flags stale data', () => {
    const live = matchFixture({
      status: 'live',
      live_state: { score: null, server_player_id: 'ply_opp' },
      freshness: {
        provider: 'fake',
        source_updated_at: null,
        observed_at: '2026-09-08T09:00:00Z',
        is_stale: true,
        age_seconds: 3600,
      },
    })

    const status = toCurrentStatus(live, 'ply_self', NOW)

    expect(status.kind).toBe('live')
    if (status.kind !== 'live') return
    expect(status.score).toBe('比分暂无')
    expect(status.detail).toBe('当前由 Casper Ruud 发球')
    expect(status.freshness).toBe('数据较旧')
  })

  it('maps a scheduled match onto the next card in Macau time', () => {
    const next = matchFixture({ status: 'scheduled', scheduled_at: '2026-09-08T13:30:00Z', winner_player_id: null })

    expect(toCurrentStatus(next, 'ply_self', NOW)).toMatchObject({
      kind: 'next',
      matchId: 'mat_1',
      event: 'Fake ATP Event 1',
      round: '1st Round',
      startLabel: '9月8日 21:30',
      countdown: '澳门时间',
    })
  })
})

describe('resultsHistoryState', () => {
  function pageFixture(overrides: Partial<PlayerResultPageDto> = {}): PlayerResultPageDto {
    return {
      player: { id: 'ply_self', name: 'Ben Shelton', localized_name: null, country_code: 'usa', ranking: 9 },
      season: 2026,
      tiers: [],
      outcome: 'all',
      page: 1,
      page_size: 20,
      total: 3,
      matches: [],
      availability: 'available',
      ...overrides,
    }
  }

  it('maps availability and emptiness onto v0 history states', () => {
    expect(resultsHistoryState(pageFixture())).toBe('ready')
    expect(resultsHistoryState(pageFixture({ total: 0 }))).toBe('empty')
    expect(resultsHistoryState(pageFixture({ availability: 'partial' }))).toBe('partial')
    expect(resultsHistoryState(pageFixture({ availability: 'stale' }))).toBe('stale')
    expect(resultsHistoryState(pageFixture({ availability: 'unavailable', total: 0 }))).toBe('unavailable')
  })
})

describe('directory presentation helpers', () => {
  it('offers production country options including China and Hong Kong', () => {
    const chn = PRODUCTION_COUNTRY_OPTIONS.find((option) => option.code === 'CHN')
    const hkg = PRODUCTION_COUNTRY_OPTIONS.find((option) => option.code === 'HKG')

    expect(chn).toMatchObject({ name: '中国' })
    expect(hkg).toMatchObject({ name: '中国香港' })
    expect(chn?.flagUrl).toContain('/cn.png')
  })

  it('maps view tiers onto canonical circuit tiers', () => {
    expect(viewTierToCircuitTier('ATP')).toBe('atp')
    expect(viewTierToCircuitTier('WTA')).toBe('wta')
    expect(viewTierToCircuitTier('Challenger')).toBe('challenger')
    expect(viewTierToCircuitTier('ITF')).toBe('itf')
    expect(viewTierToCircuitTier('Other')).toBe('other')
  })
})
