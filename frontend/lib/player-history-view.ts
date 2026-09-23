import type { PlayerHistoryContextDto, PlayerSeasonRecordDto, StructuredData } from '@/lib/api/types'

export const HISTORY_EMPTY_RESULTS_COPY = '该范围暂无赛果信息'
export const HISTORY_SEASON_UNAVAILABLE_COPY = '该赛季战绩暂不可用'

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
  return history.scope === 'season' ? HISTORY_SEASON_UNAVAILABLE_COPY : HISTORY_EMPTY_RESULTS_COPY
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
