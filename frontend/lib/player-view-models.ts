import type {
  CircuitTier,
  MatchDto,
  PlayerProfileViewDto,
  PlayerResultPageDto,
  PlayerResultSummaryDto,
  PlayerSearchResolutionDto,
  PlayerSeasonRecordDto,
  PlayerSummaryDto,
  RankingEntryDto,
  RankingPageDto,
} from '@/lib/api/types'
import type {
  CompetitionTier,
  CountryPreview,
  PlayerCurrentStatusPreview,
  PlayerDirectoryEntry,
  PlayerHistoryState,
  PlayerProfilePreview,
  PlayerResultPreview,
  PlayerSeasonSummaryPreview,
  RankMovement,
  TourKey,
} from '@/components/players/player-preview-data'
import { COUNTRY_METADATA, countryPresentation, formatAsOf } from '@/lib/view-models'

/**
 * Production mappings from the versioned REST DTOs onto the frozen v0 view
 * shapes. These functions never invent data: every missing structured field
 * stays `null` so the components render their existing unavailable copy.
 */

export const EMPTY_CURRENT_STATUS_MESSAGE = '当前没有可用的正在进行或即将开始的单打比赛。'
export const MISSING_SCORE_LABEL = '比分暂无'
export const MISSING_ROUND_LABEL = '轮次暂无'
export const MISSING_TIME_LABEL = '时间暂无'
export const BEIJING_TIMEZONE_LABEL = '北京时间'

const SURFACE_LABELS: Record<string, string> = {
  hard: '硬地',
  clay: '红土',
  grass: '草地',
}

const TIER_LABELS: Record<string, CompetitionTier> = {
  atp: 'ATP',
  wta: 'WTA',
  challenger: 'Challenger',
  itf: 'ITF',
}

const beijingPartsFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  month: 'numeric',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})
const beijingDateFormatter = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
})

function beijingCalendarDate(date: Date): { year: number; month: number; day: number } {
  const parts = beijingDateFormatter.formatToParts(date)
  const valueOf = (type: string) => Number(parts.find((part) => part.type === type)?.value)
  return { year: valueOf('year'), month: valueOf('month'), day: valueOf('day') }
}

export function beijingCalendarYear(now: Date = new Date()): number {
  return beijingCalendarDate(now).year
}

function beijingDateKey(iso: string): string | null {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return null
  const { year, month, day } = beijingCalendarDate(date)
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

export const PRODUCTION_COUNTRY_OPTIONS: CountryPreview[] = Object.entries(COUNTRY_METADATA)
  .filter(([code]) => code !== 'world')
  .map(([code, metadata]) => ({
    code: code.toUpperCase(),
    name: metadata.name,
    flagUrl: metadata.alpha2 ? `https://flagcdn.com/w40/${metadata.alpha2}.png` : null,
  }))
  .sort((a, b) => a.code.localeCompare(b.code))

export function viewTierToCircuitTier(tier: CompetitionTier): CircuitTier {
  switch (tier) {
    case 'ATP':
      return 'atp'
    case 'WTA':
      return 'wta'
    case 'Challenger':
      return 'challenger'
    case 'ITF':
      return 'itf'
    default:
      return 'other'
  }
}

export function movementFor(direction: RankingEntryDto['movement']): RankMovement {
  if (direction === 'up') return { direction: 'up', places: null }
  if (direction === 'down') return { direction: 'down', places: null }
  if (direction === 'same') return { direction: 'flat', places: 0 }
  return { direction: 'unknown', places: null }
}

function shortNameFrom(name: string): string {
  const parts = name.trim().split(/\s+/)
  return parts[parts.length - 1] || name
}

function entryFromSummary(
  player: PlayerSummaryDto,
  options: { tour: TourKey | null; rank: number | null; points: number | null; avatarUrl: string | null; movement?: RankMovement },
): PlayerDirectoryEntry {
  return {
    id: player.id,
    tour: options.tour,
    name: player.name,
    nameZh: player.localized_name ?? null,
    shortName: shortNameFrom(player.name),
    ...countryPresentation(player.country_code, player.country_alpha2 ?? null),
    rank: options.rank,
    points: options.points,
    movement: options.movement ?? movementFor('unknown'),
    avatarUrl: options.avatarUrl,
    aliases: [],
  }
}

export function toDirectoryEntry(entry: RankingEntryDto): PlayerDirectoryEntry {
  return entryFromSummary(entry.player, {
    tour: entry.tour,
    rank: entry.rank,
    points: entry.points,
    avatarUrl: null,
    movement: movementFor(entry.movement),
  })
}

export function searchResolutionToEntries(resolution: PlayerSearchResolutionDto): PlayerDirectoryEntry[] {
  if (resolution.status === 'resolved' && resolution.player) {
    return [
      entryFromSummary(resolution.player, {
        tour: null,
        rank: resolution.player.ranking,
        points: null,
        avatarUrl: null,
      }),
    ]
  }
  if (resolution.status === 'ambiguous') {
    return resolution.candidates.map((candidate) =>
      entryFromSummary(candidate.player, {
        tour: null,
        rank: candidate.current_rank ?? candidate.player.ranking,
        points: null,
        avatarUrl: null,
      }),
    )
  }
  return []
}

export function toSeasonSummary(
  season: number,
  record: PlayerSeasonRecordDto | null,
  recordedResults: PlayerResultSummaryDto | null = null,
): PlayerSeasonSummaryPreview {
  const hasCompleteProviderRecord =
    record !== null
    && record.matches_won !== null
    && record.matches_lost !== null
  const useRecordedResults = !hasCompleteProviderRecord && recordedResults !== null
  const wins = useRecordedResults && recordedResults
    ? recordedResults.matches_won
    : record?.matches_won ?? null
  const losses = useRecordedResults && recordedResults
    ? recordedResults.matches_lost
    : record?.matches_lost ?? null
  const matches = useRecordedResults
    ? recordedResults?.matches ?? null
    : wins === null || losses === null
      ? null
      : wins + losses
  return {
    season: record?.season ?? season,
    matches,
    wins,
    losses,
    winRate: matches !== null && matches > 0 && wins !== null
      ? Number(((wins / matches) * 100).toFixed(1))
      : null,
    titles: record?.titles ?? null,
    hard: record?.hard ? { won: record.hard.won, lost: record.hard.lost } : null,
    clay: record?.clay ? { won: record.clay.won, lost: record.clay.lost } : null,
    grass: record?.grass ? { won: record.grass.won, lost: record.grass.lost } : null,
    ...(useRecordedResults ? { resultBasis: 'recorded_results' as const } : {}),
  }
}

function ageFrom(birthDate: string, now: Date): number | null {
  const [year, month, day] = birthDate.split('-').map(Number)
  if (!year || !month || !day) return null
  const current = beijingCalendarDate(now)
  let age = current.year - year
  if (current.month < month || (current.month === month && current.day < day)) age -= 1
  return age >= 0 ? age : null
}

export function toProfilePreview(view: PlayerProfileViewDto, now: Date = new Date()): PlayerProfilePreview {
  const base = entryFromSummary(view.profile.player, {
    tour: view.ranking?.tour ?? null,
    rank: view.ranking?.rank ?? null,
    points: view.ranking?.points ?? null,
    avatarUrl: view.profile.image_url,
    movement: movementFor(view.ranking?.movement ?? 'unknown'),
  })
  return {
    ...base,
    birthDate: view.profile.birth_date,
    age: view.profile.birth_date ? ageFrom(view.profile.birth_date, now) : null,
    rankUpdatedAt: view.ranking?.fetched_at ?? null,
  }
}

function opponentOf(match: MatchDto, playerId: string): MatchDto['players'][number] {
  return match.players.find((player) => player.id !== playerId) ?? match.players[1] ?? match.players[0]
}

function displayRoundLabel(round: string | null, tournament: string): string | null {
  const label = round?.trim()
  const tournamentName = tournament.trim()
  if (!label || !tournamentName) return label || null

  const separator = label.indexOf(' - ')
  if (separator < 0) return label

  const eventLabel = label.slice(0, separator).trim()
  const prefixLength = eventLabel.length - tournamentName.length
  if (prefixLength < 0) return label
  if (eventLabel.slice(prefixLength).toLocaleLowerCase() !== tournamentName.toLocaleLowerCase()) {
    return label
  }

  const tourLabel = eventLabel.slice(0, prefixLength).trim()
  if (tourLabel && !/^(?:ATP|WTA|ITF|Challenger(?:\s+(?:Men|Women))?)$/i.test(tourLabel)) {
    return label
  }
  return label.slice(separator + 3).trim() || label
}

/** Formats set (and live point) scores from the profiled player's perspective. */
export function formatMatchScore(match: MatchDto, playerId: string): string | null {
  const score = match.live_state?.score
  if (!score) return null
  const side = match.players[1]?.id === playerId ? 2 : 1
  const other = side === 1 ? 2 : 1
  const hasSetCount = score.sets_won !== null && score.sets_won.some((sets) => sets > 0)
  const reportedGames = score.sets.flatMap((set) => {
    const selfGames = side === 1 ? set.player1_games : set.player2_games
    const otherGames = side === 1 ? set.player2_games : set.player1_games
    const selfTiebreak = side === 1
      ? set.player1_tiebreak_points
      : set.player2_tiebreak_points
    const otherTiebreak = side === 1
      ? set.player2_tiebreak_points
      : set.player1_tiebreak_points
    if (selfGames === null || otherGames === null) return []
    const tiebreak =
      selfTiebreak != null && otherTiebreak != null
        ? `（${selfTiebreak}–${otherTiebreak}）`
        : ''
    return [`${selfGames}–${otherGames}${tiebreak}`]
  })
  const setCount = hasSetCount
    ? `${score.sets_won![side - 1]}–${score.sets_won![other - 1]} 盘`
    : ''
  const knownSetCount = score.sets_won?.reduce((total, sets) => total + sets, 0) ?? 0
  const hasMissingSetScores = reportedGames.length < Math.max(score.sets.length, knownSetCount)
  const gamesLabel =
    match.status === 'finished' && hasMissingSetScores && reportedGames.length > 0
      ? `部分局分：${reportedGames.join(' ')}`
      : reportedGames.join(' ')
  const sets =
    setCount && hasMissingSetScores
      ? [setCount, gamesLabel || null].filter(Boolean).join(' · ')
      : gamesLabel || setCount
  const selfPoint = score.points[side - 1]
  const otherPoint = score.points[other - 1]
  if (match.status === 'live' && selfPoint && otherPoint) {
    const currentPoint = `${selfPoint}–${otherPoint}`
    return sets ? `${sets} · ${currentPoint}` : currentPoint
  }
  return sets || null
}

export function toResultPreview(match: MatchDto, playerId: string, fallbackSeason: number): PlayerResultPreview {
  const opponentPlayer = opponentOf(match, playerId)
  const date = match.scheduled_at ? beijingDateKey(match.scheduled_at) : null
  return {
    id: match.id,
    matchId: match.id,
    season: date ? Number(date.slice(0, 4)) : fallbackSeason,
    date,
    tournament: match.tournament.name,
    tournamentZh: null,
    tier: TIER_LABELS[match.tournament.circuit ?? ''] ?? 'Other',
    surface: match.surface ? (SURFACE_LABELS[match.surface] ?? match.surface) : null,
    round: displayRoundLabel(match.round, match.tournament.name),
    opponent: {
      name: opponentPlayer.name,
      nameZh: opponentPlayer.localized_name ?? null,
      ...countryPresentation(opponentPlayer.country_code, opponentPlayer.country_alpha2 ?? null),
    },
    outcome:
      match.winner_player_id === null
        ? 'unknown'
        : match.winner_player_id === playerId
          ? 'win'
          : 'loss',
    score: formatMatchScore(match, playerId),
  }
}

function freshnessNote(match: MatchDto): string {
  if (match.freshness.is_stale) return '数据可能延迟'
  const ageSeconds = match.freshness.age_seconds
  if (ageSeconds < 60) return '刚刚更新'
  return `${Math.max(1, Math.floor(ageSeconds / 60))} 分钟前更新`
}

function beijingStartLabel(iso: string | null): string {
  if (!iso) return MISSING_TIME_LABEL
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return MISSING_TIME_LABEL
  const parts = beijingPartsFormatter.formatToParts(date)
  const valueOf = (type: string) => parts.find((part) => part.type === type)?.value ?? ''
  return `${valueOf('month')}月${valueOf('day')}日 ${valueOf('hour')}:${valueOf('minute')}`
}

export function toCurrentStatus(
  match: MatchDto | null,
  playerId: string,
  now: Date = new Date(),
): PlayerCurrentStatusPreview {
  void now
  if (!match) {
    return { kind: 'none', message: EMPTY_CURRENT_STATUS_MESSAGE }
  }
  const opponentPlayer = opponentOf(match, playerId)
  const opponent = {
    name: opponentPlayer.name,
    nameZh: opponentPlayer.localized_name ?? null,
    ...countryPresentation(opponentPlayer.country_code, opponentPlayer.country_alpha2 ?? null),
  }
  const round = displayRoundLabel(match.round, match.tournament.name) ?? MISSING_ROUND_LABEL

  if (match.status === 'live') {
    const serverId = match.live_state?.server_player_id ?? null
    const detail =
      serverId === null
        ? '发球方暂无'
        : serverId === playerId
          ? '当前由本球员发球'
          : `当前由 ${opponentPlayer.name} 发球`
    return {
      kind: 'live',
      matchId: match.id,
      event: match.tournament.name,
      round,
      opponent,
      score: formatMatchScore(match, playerId) ?? MISSING_SCORE_LABEL,
      detail,
      freshness: freshnessNote(match),
    }
  }

  return {
    kind: 'next',
    matchId: match.id,
    event: match.tournament.name,
    round,
    opponent,
    startLabel: beijingStartLabel(match.scheduled_at),
    countdown: BEIJING_TIMEZONE_LABEL,
  }
}

export type ResultsReadyState = Extract<
  PlayerHistoryState,
  'ready' | 'empty' | 'partial' | 'unavailable' | 'stale'
>

export function playerResultSeasons(currentSeason: number): number[] {
  return Array.from({ length: 5 }, (_, index) => currentSeason - index)
}

export function resultsHistoryState(page: PlayerResultPageDto): ResultsReadyState {
  if (page.availability === 'unavailable') return 'unavailable'
  if (page.availability === 'stale') return 'stale'
  if (page.availability === 'partial') return 'partial'
  return page.total === 0 ? 'empty' : 'ready'
}

/** Concise availability notice copy for ranking pages; null when fully available. */
export function rankingsAvailabilityNotice(
  availability: RankingPageAvailability,
): string | null {
  if (availability === 'stale') return '正在显示最近一次成功快照；排名可能不是最新。'
  if (availability === 'partial') return '当前数据源只返回部分排名；已显示可用记录。'
  return null
}

export type RankingPageAvailability = RankingPageDto['availability']

/** Header note for the production directory: the snapshot instant, truthfully. */
export function rankingsSnapshotNote(asOf: string | null): string {
  if (asOf === null) return '更新时间暂不可用'
  const formatted = formatAsOf(asOf)
  return formatted ? `更新于 ${formatted}（北京时间）` : '更新时间暂不可用'
}
