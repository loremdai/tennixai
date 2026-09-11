import type {
  MatchDto,
  MatchScoreDto,
  MatchStatus,
  MomentumObservationDto,
  PointEventDto,
} from '@/lib/api/types'

export type HomeMatchViewModel = {
  id: string
  href: string
  status: 'upcoming' | 'live' | 'finished' | 'unavailable'
  tournament: string
  round: string
  time: string
  surface: string
  players: [string, string]
  score?: {
    rows: [
      { player: string; sets: string[]; points: string; serving: boolean },
      { player: string; sets: string[]; points: string; serving: boolean },
    ]
  }
  freshnessLabel: string
  isStale: boolean
}

export type MatchViewModel = {
  id: string
  canonicalStatus: MatchStatus
  visualStatus: 'upcoming' | 'live' | 'finished' | 'unavailable'
  tournament: string
  round: string
  surface: string
  scheduledDate: string
  scheduledTime: string
  timezoneLabel: '澳门时间'
  format: string
  indoorLabel: string
  players: [
    { id: string; name: string; shortName: string; initials: string; countryCode: string; ranking: number | null },
    { id: string; name: string; shortName: string; initials: string; countryCode: string; ranking: number | null },
  ]
  score: MatchScoreDto | null
  serverPlayerId: string | null
  winnerPlayerId: string | null
  freshnessLabel: string
  isStale: boolean
}

const OFFICIAL_MISSING_ROUND = '官方未返回轮次'
const OFFICIAL_MISSING_SURFACE = '官方未返回场地类型'
const OFFICIAL_MISSING_INDOOR = '官方未返回室内外'
const OFFICIAL_MISSING_FORMAT = '官方未返回赛制'
const OFFICIAL_MISSING_COUNTRY = '官方未提供国家代码'
const OFFICIAL_MISSING_DATE = '官方未返回开赛日期'
const OFFICIAL_MISSING_TIME = '官方未返回开赛时间'

const timeFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Macau',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

const dateFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Macau',
  month: 'long',
  day: 'numeric',
})

const SURFACE_LABELS: Record<string, string> = {
  hard: '硬地',
  clay: '红土',
  grass: '草地',
}

function toVisualStatus(status: MatchStatus): HomeMatchViewModel['status'] {
  if (status === 'scheduled') return 'upcoming'
  if (status === 'live') return 'live'
  if (status === 'finished') return 'finished'
  return 'unavailable'
}

function formatTime(iso: string | null): string {
  if (!iso) return OFFICIAL_MISSING_TIME
  return timeFormatter.format(new Date(iso))
}

function formatDate(iso: string | null): string {
  if (!iso) return OFFICIAL_MISSING_DATE
  return dateFormatter.format(new Date(iso))
}

function surfaceLabel(surface: string | null, indoor: boolean | null): string {
  if (!surface) {
    return indoor === null
      ? OFFICIAL_MISSING_SURFACE
      : `${indoor ? '室内' : '室外'} · ${OFFICIAL_MISSING_SURFACE}`
  }
  const base = SURFACE_LABELS[surface] ?? surface
  return indoor ? `室内${base}` : base
}

function shortName(name: string): string {
  const parts = name.trim().split(/\s+/)
  return parts[parts.length - 1] || name
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return ''
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

function freshnessLabel(match: MatchDto): string {
  if (match.freshness.is_stale) {
    return `数据较旧 · ${match.freshness.age_seconds} 秒未刷新`
  }
  return `更新于 ${formatTime(match.freshness.observed_at)}`
}

function matchHref(match: MatchDto): string {
  return `/matches/${encodeURIComponent(match.id)}`
}

export function toHomeMatch(match: MatchDto): HomeMatchViewModel {
  const score = match.live_state?.score ?? null
  const view: HomeMatchViewModel = {
    id: match.id,
    href: matchHref(match),
    status: toVisualStatus(match.status),
    tournament: match.tournament.name,
    round: match.round ?? OFFICIAL_MISSING_ROUND,
    time: match.status === 'live' ? '进行中' : formatTime(match.scheduled_at),
    surface: surfaceLabel(match.surface, match.indoor),
    players: [shortName(match.players[0].name), shortName(match.players[1].name)],
    freshnessLabel: freshnessLabel(match),
    isStale: match.freshness.is_stale,
  }

  if (score) {
    const serverId = match.live_state?.server_player_id ?? null
    view.score = {
      rows: [
        {
          player: shortName(match.players[0].name),
          sets: score.sets.map((set) => String(set.player1_games ?? '-')),
          points: score.points[0] ?? '',
          serving: serverId === match.players[0].id,
        },
        {
          player: shortName(match.players[1].name),
          sets: score.sets.map((set) => String(set.player2_games ?? '-')),
          points: score.points[1] ?? '',
          serving: serverId === match.players[1].id,
        },
      ],
    }
  }

  return view
}

export function toMatchViewModel(match: MatchDto): MatchViewModel {
  return {
    id: match.id,
    canonicalStatus: match.status,
    visualStatus: toVisualStatus(match.status),
    tournament: match.tournament.name,
    round: match.round ?? OFFICIAL_MISSING_ROUND,
    surface: surfaceLabel(match.surface, match.indoor),
    scheduledDate: formatDate(match.scheduled_at),
    scheduledTime: formatTime(match.scheduled_at),
    timezoneLabel: '澳门时间',
    format: match.format ? (match.format === 'BO5' ? '五盘三胜 · BO5' : `三盘两胜 · ${match.format}`) : OFFICIAL_MISSING_FORMAT,
    indoorLabel: match.indoor === null ? OFFICIAL_MISSING_INDOOR : match.indoor ? '室内' : '室外',
    players: [
      {
        id: match.players[0].id,
        name: match.players[0].name,
        shortName: shortName(match.players[0].name),
        initials: initials(match.players[0].name),
        countryCode: (match.players[0].country_code ?? OFFICIAL_MISSING_COUNTRY).toUpperCase(),
        ranking: match.players[0].ranking,
      },
      {
        id: match.players[1].id,
        name: match.players[1].name,
        shortName: shortName(match.players[1].name),
        initials: initials(match.players[1].name),
        countryCode: (match.players[1].country_code ?? OFFICIAL_MISSING_COUNTRY).toUpperCase(),
        ranking: match.players[1].ranking,
      },
    ],
    score: match.live_state?.score ?? null,
    serverPlayerId: match.live_state?.server_player_id ?? null,
    winnerPlayerId: match.winner_player_id,
    freshnessLabel: freshnessLabel(match),
    isStale: match.freshness.is_stale,
  }
}

export type StatGroup = '发球' | '接发' | '关键分' | '制胜与失误' | '体能' | '总计'

export type StatMeta = { label: string; unit: 'count' | 'percent' | 'km/h' | 'm'; group: StatGroup }

export const STAT_GROUP_ORDER: StatGroup[] = ['发球', '接发', '关键分', '制胜与失误', '体能', '总计']

export const STAT_META: Record<string, StatMeta> = {
  aces: { label: 'ACE 球', unit: 'count', group: '发球' },
  double_faults: { label: '双误', unit: 'count', group: '发球' },
  first_serve_percentage: { label: '一发成功率', unit: 'percent', group: '发球' },
  first_serve_points_won: { label: '一发得分率', unit: 'percent', group: '发球' },
  second_serve_points_won: { label: '二发得分率', unit: 'percent', group: '发球' },
  service_points_won: { label: '发球得分率', unit: 'percent', group: '发球' },
  service_games_won: { label: '发球局胜率', unit: 'percent', group: '发球' },
  return_points_won: { label: '接发得分率', unit: 'percent', group: '接发' },
  first_return_points_won: { label: '一发接发得分率', unit: 'percent', group: '接发' },
  second_return_points_won: { label: '二发接发得分率', unit: 'percent', group: '接发' },
  return_games_won: { label: '接发局胜率', unit: 'percent', group: '接发' },
  break_points_saved: { label: '破发点挽救率', unit: 'percent', group: '关键分' },
  break_points_converted: { label: '破发点转化率', unit: 'percent', group: '关键分' },
  match_points_saved: { label: '赛点挽救', unit: 'count', group: '关键分' },
  winners: { label: '制胜分', unit: 'count', group: '制胜与失误' },
  unforced_errors: { label: '非受迫性失误', unit: 'count', group: '制胜与失误' },
  net_points_won: { label: '上网得分率', unit: 'percent', group: '制胜与失误' },
  average_first_serve_speed: { label: '一发平均速度', unit: 'km/h', group: '体能' },
  average_second_serve_speed: { label: '二发平均速度', unit: 'km/h', group: '体能' },
  distance_covered: { label: '跑动距离', unit: 'm', group: '体能' },
  total_points_won: { label: '总得分', unit: 'count', group: '总计' },
  total_games_won: { label: '总赢局', unit: 'count', group: '总计' },
}

export function formatStatValue(value: number | null, unit: string): string {
  if (value === null) return '官方未返回'
  if (unit === 'percent') return `${trimNumber(value)}%`
  if (unit === 'count') return trimNumber(value)
  return `${trimNumber(value)} ${unit}`
}

function trimNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : String(Math.round(value * 10) / 10)
}

const asOfFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Macau',
  month: 'long',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

/** Formats a snapshot `as_of` timestamp for display; null stays null (missing, not guessed). */
export function formatAsOf(iso: string | null): string | null {
  if (!iso) return null
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return null
  return asOfFormatter.format(date)
}

export type MomentumChartPoint = {
  sequence: number
  value: number
  isKeyPoint: boolean
}

export function toMomentumChart(
  observations: MomentumObservationDto[],
  points: PointEventDto[],
): MomentumChartPoint[] {
  const keyPointSequences = new Set(
    points
      .filter((point) => point.is_break_point || point.is_set_point || point.is_match_point)
      .map((point) => point.sequence),
  )
  return observations
    .slice()
    .sort((a, b) => a.point_sequence - b.point_sequence)
    .slice(-20)
    .map((observation) => ({
      sequence: observation.point_sequence,
      value: observation.value,
      isKeyPoint: keyPointSequences.has(observation.point_sequence),
    }))
}
