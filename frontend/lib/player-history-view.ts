import type { PlayerHistoryContextDto, PlayerSeasonRecordDto, StructuredData } from '@/lib/api/types'

export const HISTORY_EMPTY_RESULTS_COPY = '该范围暂无赛果信息'
export const HISTORY_SEASON_UNAVAILABLE_COPY = '该赛季战绩暂不可用'
export const HISTORY_RESULTS_UNAVAILABLE_COPY = '赛果暂不可用'
export const HISTORY_PARTIAL_EMPTY_COPY = '赛果数据可能不完整，暂未找到结果'
export const HISTORY_STALE_EMPTY_COPY = '赛果数据可能已过时，暂未找到结果'

export function historyScopeLabel(history: PlayerHistoryContextDto): string {
  switch (history.scope) {
    case 'yesterday':
      return '昨日赛果'
    case 'last':
      return '上一场比赛'
    case 'recent':
      return '近期赛果'
    case 'season':
      return `${history.season} 赛季战绩`
  }
}

export function historyPlayerHeading(history: PlayerHistoryContextDto): string {
  const { name, localized_name: localizedName } = history.player
  return localizedName ? `${name}（${localizedName}）` : name
}

/** Query-level title for a single history result: `<player> · <scope label>`. */
export function playerHistoryTitle(data: StructuredData): string {
  const history = data.player_history
  if (!history) return '球员赛果与战绩'
  return `${historyPlayerHeading(history)} · ${historyScopeLabel(history)}`
}

export function historyEmptyCopy(history: PlayerHistoryContextDto): string {
  if (history.scope === 'season' || history.empty_reason === 'season_record_unavailable') {
    return HISTORY_SEASON_UNAVAILABLE_COPY
  }
  if (history.availability === 'unavailable') return HISTORY_RESULTS_UNAVAILABLE_COPY
  if (history.availability === 'partial') return HISTORY_PARTIAL_EMPTY_COPY
  if (history.availability === 'stale') return HISTORY_STALE_EMPTY_COPY
  return HISTORY_EMPTY_RESULTS_COPY
}

/** A concise caveat for result rows that are present but not known to be complete/current. */
export function historyQualityCopy(history: PlayerHistoryContextDto): string | null {
  if (history.scope === 'season') return null
  if (history.availability === 'partial') return '赛果数据可能不完整'
  if (history.availability === 'stale') return '赛果数据可能已过时'
  return null
}

/** Win rate only from supplied wins/losses; null denominator stays unknown. */
export function seasonWinRate(record: PlayerSeasonRecordDto): string | null {
  if (record.matches_won === null || record.matches_lost === null) return null
  const total = record.matches_won + record.matches_lost
  if (total <= 0) return null
  return `${Math.round((record.matches_won / total) * 100)}%`
}

export function seasonSurfaceEntries(
  record: PlayerSeasonRecordDto,
): Array<{ label: string; text: string }> {
  const entries: Array<{ label: string; text: string }> = []
  const format = (value: number | null) => value === null ? '—' : String(value)
  if (record.hard) entries.push({ label: '硬地', text: `${format(record.hard.won)}-${format(record.hard.lost)}` })
  if (record.clay) entries.push({ label: '红土', text: `${format(record.clay.won)}-${format(record.clay.lost)}` })
  if (record.grass) entries.push({ label: '草地', text: `${format(record.grass.won)}-${format(record.grass.lost)}` })
  return entries
}
