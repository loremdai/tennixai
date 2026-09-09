import { describe, expect, it } from 'vitest'

import type { CircuitTier, Discipline, Gender, MatchDto } from '@/lib/api/types'

import {
  CIRCUIT_LABELS,
  DEFAULT_MATCH_FILTERS,
  DISCIPLINE_LABELS,
  GENDER_LABELS,
  filterMatches,
  isDefaultFilters,
  sortCatalogMatches,
  toggleFilterValue,
  type MatchFiltersState,
} from './match-filters'

function makeMatch(
  id: string,
  circuit: CircuitTier,
  gender: Gender,
  discipline: Discipline,
  overrides: Partial<MatchDto> = {},
): MatchDto {
  return {
    id,
    status: 'scheduled',
    players: [
      { id: `ply_${id}_1`, name: `Player One ${id}`, country_code: null, ranking: null },
      { id: `ply_${id}_2`, name: `Player Two ${id}`, country_code: null, ranking: null },
    ],
    tournament: { id: `trn_${id}`, name: `Event ${id}`, tour: null, circuit, gender, discipline },
    scheduled_at: '2026-09-10T12:00:00Z',
    round: null,
    surface: null,
    indoor: null,
    format: null,
    live_state: null,
    winner_player_id: null,
    freshness: {
      provider: 'fake',
      source_updated_at: null,
      observed_at: '2026-09-09T12:00:00Z',
      is_stale: false,
      age_seconds: 0,
    },
    ...overrides,
  }
}

const matches: MatchDto[] = [
  makeMatch('mat_atp_men_singles', 'atp', 'men', 'singles'),
  makeMatch('mat_wta_women_singles', 'wta', 'women', 'singles'),
  makeMatch('mat_challenger_men_singles', 'challenger', 'men', 'singles'),
  makeMatch('mat_itf_women_doubles', 'itf', 'women', 'doubles'),
  makeMatch('mat_other_unknown', 'other', 'unknown', 'unknown'),
]

describe('DEFAULT_MATCH_FILTERS', () => {
  it('uses the approved default facets', () => {
    expect(DEFAULT_MATCH_FILTERS).toEqual({
      circuits: ['atp', 'wta'],
      genders: [],
      disciplines: ['singles'],
    })
  })

  it('is recognized by isDefaultFilters and not after any toggle', () => {
    expect(isDefaultFilters(DEFAULT_MATCH_FILTERS)).toBe(true)
    const toggled = toggleFilterValue(DEFAULT_MATCH_FILTERS, 'circuits', 'itf')
    expect(isDefaultFilters(toggled)).toBe(false)
  })
})

describe('filterMatches', () => {
  it('stacks circuit, gender, and discipline without relaxing filters', () => {
    const result = filterMatches(matches, {
      circuits: ['itf'],
      genders: ['women'],
      disciplines: ['doubles'],
    })
    expect(result.map((match) => match.id)).toEqual(['mat_itf_women_doubles'])
  })

  it('applies the approved defaults', () => {
    const result = filterMatches(matches, DEFAULT_MATCH_FILTERS)
    expect(result.map((match) => match.id)).toEqual([
      'mat_atp_men_singles',
      'mat_wta_women_singles',
    ])
  })

  it('treats an empty group as all values', () => {
    const result = filterMatches(matches, { circuits: [], genders: [], disciplines: [] })
    expect(result).toHaveLength(5)
  })

  it('keeps an empty result instead of silently relaxing', () => {
    const result = filterMatches(matches, {
      circuits: ['atp'],
      genders: ['women'],
      disciplines: ['singles'],
    })
    expect(result).toEqual([])
  })
})

describe('toggleFilterValue', () => {
  it('adds a value immutably', () => {
    const next = toggleFilterValue(DEFAULT_MATCH_FILTERS, 'circuits', 'itf')
    expect(next.circuits).toEqual(['atp', 'wta', 'itf'])
    expect(DEFAULT_MATCH_FILTERS.circuits).toEqual(['atp', 'wta'])
  })

  it('removes an existing value and allows the empty (all) state', () => {
    const onlyAtp: MatchFiltersState = { ...DEFAULT_MATCH_FILTERS, circuits: ['atp'] }
    const next = toggleFilterValue(onlyAtp, 'circuits', 'atp')
    expect(next.circuits).toEqual([])
  })

  it('never auto-selects another value when the combination becomes empty', () => {
    const next = toggleFilterValue(DEFAULT_MATCH_FILTERS, 'disciplines', 'singles')
    expect(next.disciplines).toEqual([])
  })
})

describe('sortCatalogMatches', () => {
  it('orders by tier, then live, then start time, then id', () => {
    const itfLive = makeMatch('mat_a_itf_live', 'itf', 'men', 'singles', {
      status: 'live',
      scheduled_at: '2026-09-09T01:00:00Z',
    })
    const atpUpcoming = makeMatch('mat_b_atp_upcoming', 'atp', 'men', 'singles', {
      scheduled_at: '2026-09-12T01:00:00Z',
    })
    const atpLiveLate = makeMatch('mat_c_atp_live_late', 'atp', 'men', 'singles', {
      status: 'live',
      scheduled_at: '2026-09-11T01:00:00Z',
    })
    const sorted = sortCatalogMatches([itfLive, atpUpcoming, atpLiveLate])
    expect(sorted.map((match) => match.id)).toEqual([
      'mat_c_atp_live_late',
      'mat_b_atp_upcoming',
      'mat_a_itf_live',
    ])
  })

  it('breaks ties deterministically by id', () => {
    const a = makeMatch('mat_zzz', 'atp', 'men', 'singles', { scheduled_at: '2026-09-10T00:00:00Z' })
    const b = makeMatch('mat_aaa', 'atp', 'men', 'singles', { scheduled_at: '2026-09-10T00:00:00Z' })
    expect(sortCatalogMatches([a, b]).map((match) => match.id)).toEqual(['mat_aaa', 'mat_zzz'])
  })
})

describe('labels', () => {
  it('covers every canonical facet value exactly once', () => {
    expect(Object.keys(CIRCUIT_LABELS).sort()).toEqual(['atp', 'challenger', 'itf', 'other', 'wta'])
    expect(Object.keys(GENDER_LABELS).sort()).toEqual(['men', 'mixed', 'unknown', 'women'])
    expect(Object.keys(DISCIPLINE_LABELS).sort()).toEqual(['doubles', 'singles', 'team', 'unknown'])
    expect(CIRCUIT_LABELS.other).toBe('其他')
    expect(GENDER_LABELS.women).toBe('女子')
    expect(DISCIPLINE_LABELS.singles).toBe('单打')
  })
})
