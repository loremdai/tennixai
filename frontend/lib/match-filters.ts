import type {
  CircuitTier,
  Discipline,
  Gender,
  MatchDto,
  MatchFiltersDto,
} from '@/lib/api/types'

export type MatchFiltersState = MatchFiltersDto

export type FacetGroup = 'circuits' | 'genders' | 'disciplines'

export const DEFAULT_MATCH_FILTERS: MatchFiltersState = {
  circuits: ['atp', 'wta'],
  genders: [],
  disciplines: ['singles'],
}

export const CIRCUIT_ORDER: CircuitTier[] = ['atp', 'wta', 'challenger', 'itf', 'other']
export const GENDER_ORDER: Gender[] = ['men', 'women', 'mixed', 'unknown']
export const DISCIPLINE_ORDER: Discipline[] = ['singles', 'doubles', 'team', 'unknown']

export const CIRCUIT_LABELS: Record<CircuitTier, string> = {
  atp: 'ATP',
  wta: 'WTA',
  challenger: 'Challenger',
  itf: 'ITF',
  other: '其他',
}

export const GENDER_LABELS: Record<Gender, string> = {
  men: '男子',
  women: '女子',
  mixed: '混合',
  unknown: '未知',
}

export const DISCIPLINE_LABELS: Record<Discipline, string> = {
  singles: '单打',
  doubles: '双打',
  team: '团体',
  unknown: '未知',
}

const CIRCUIT_PRIORITY: Record<CircuitTier, number> = {
  atp: 0,
  wta: 0,
  challenger: 1,
  itf: 2,
  other: 3,
}

const MAX_TIME = Number.MAX_SAFE_INTEGER

function scheduledTime(match: MatchDto): number {
  if (!match.scheduled_at) return MAX_TIME
  const time = new Date(match.scheduled_at).getTime()
  return Number.isNaN(time) ? MAX_TIME : time
}

/** Mirrors the backend catalog_sort_key: tier → live → start time → id. */
export function sortCatalogMatches(matches: MatchDto[]): MatchDto[] {
  return [...matches].sort((a, b) => {
    const tier = CIRCUIT_PRIORITY[a.tournament.circuit ?? 'other'] - CIRCUIT_PRIORITY[b.tournament.circuit ?? 'other']
    if (tier !== 0) return tier
    const live = (a.status === 'live' ? 0 : 1) - (b.status === 'live' ? 0 : 1)
    if (live !== 0) return live
    const time = scheduledTime(a) - scheduledTime(b)
    if (time !== 0) return time
    return a.id < b.id ? -1 : a.id > b.id ? 1 : 0
  })
}

export function filterMatches(matches: MatchDto[], filters: MatchFiltersState): MatchDto[] {
  return matches.filter((match) => {
    const tournament = match.tournament
    if (filters.circuits.length > 0 && !filters.circuits.includes(tournament.circuit ?? 'other')) {
      return false
    }
    if (filters.genders.length > 0 && !filters.genders.includes(tournament.gender ?? 'unknown')) {
      return false
    }
    if (
      filters.disciplines.length > 0 &&
      !filters.disciplines.includes(tournament.discipline ?? 'unknown')
    ) {
      return false
    }
    return true
  })
}

export function isDefaultFilters(filters: MatchFiltersState): boolean {
  const same = (a: readonly string[], b: readonly string[]) =>
    a.length === b.length && a.every((value, index) => value === b[index])
  return (
    same(filters.circuits, DEFAULT_MATCH_FILTERS.circuits) &&
    same(filters.genders, DEFAULT_MATCH_FILTERS.genders) &&
    same(filters.disciplines, DEFAULT_MATCH_FILTERS.disciplines)
  )
}

export function toggleFilterValue<T extends string>(
  filters: MatchFiltersState,
  group: FacetGroup,
  value: T,
): MatchFiltersState {
  const current = filters[group] as string[]
  const next = current.includes(value)
    ? current.filter((item) => item !== value)
    : [...current, value]
  return { ...filters, [group]: next } as MatchFiltersState
}
