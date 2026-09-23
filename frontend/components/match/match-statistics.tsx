'use client'

import { Badge } from '@/components/ui/badge'
import type { MatchStatisticDto, PlayerDto, PointEventDto } from '@/lib/api/types'
import {
  formatAsOf,
  formatStatValue,
  STAT_GROUP_ORDER,
  STAT_META,
  type StatGroup,
} from '@/lib/view-models'

type StatisticGroupView = {
  group: StatGroup
  rows: Array<{
    name: string
    period: string
    label: string
    unit: string
    p1: number | null
    p2: number | null
    partial: boolean
    stale: boolean
    asOf: string
  }>
  missing: string[]
}

function shortName(name: string): string {
  const parts = name.trim().split(/\s+/)
  return parts[parts.length - 1] || name
}

function formatPeriod(period: string): string {
  if (period === 'match') return '全场'
  const set = /^set:(\d+)$/.exec(period)
  return set ? `第 ${set[1]} 盘` : period
}

export function MatchStatisticsCard({
  statistics,
  points,
  players,
}: {
  statistics: MatchStatisticDto[]
  points: PointEventDto[]
  players: [PlayerDto, PlayerDto]
}) {
  const known = statistics.filter((stat) => STAT_META[stat.name])
  const latestStatisticAsOf = known.reduce<string | null>((latest, stat) => {
    const observedAt = Date.parse(stat.as_of)
    if (!Number.isFinite(observedAt)) return latest
    if (latest === null || observedAt > Date.parse(latest)) return stat.as_of
    return latest
  }, null)
  const formattedAsOf = formatAsOf(latestStatisticAsOf)
  const byGroup = new Map<StatGroup, StatisticGroupView>()
  for (const stat of known) {
    const meta = STAT_META[stat.name]
    const view = byGroup.get(meta.group) ?? { group: meta.group, rows: [], missing: [] }
    view.rows.push({
      name: stat.name,
      period: stat.period,
      label: meta.label,
      unit: meta.unit,
      p1: stat.player1_value,
      p2: stat.player2_value,
      partial: stat.availability === 'partial',
      stale: stat.availability === 'stale',
      asOf: stat.as_of,
    })
    byGroup.set(meta.group, view)
  }
  // Missing canonical stats are declared inside groups that already report data.
  if (known.length > 0) {
    const present = new Set(known.map((stat) => stat.name))
    for (const [name, meta] of Object.entries(STAT_META)) {
      if (present.has(name)) continue
      const view = byGroup.get(meta.group)
      if (!view) continue
      view.missing.push(meta.label)
    }
  }
  const groups = STAT_GROUP_ORDER.flatMap((group) => {
    const view = byGroup.get(group)
    return view && view.rows.length > 0 ? [view] : []
  })

  const determinate = points.filter((point) => point.winner_player_id !== null)
  const lastTen = determinate.slice(-10)

  return (
    <div className="flex flex-col gap-5">
      {known.length === 0 ? (
        <p className="rounded-lg bg-muted/25 p-4 text-sm text-muted-foreground">
          供应商尚未返回本场技术统计；已返回的项目才会展示，缺失不会按 0 处理。
        </p>
      ) : (
        groups.map((view) => (
          <section key={view.group} aria-label={`${view.group}统计`}>
            <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {view.group}
            </h3>
            <div className="divide-y rounded-lg bg-muted/20 px-3">
              {view.rows.map((row) => (
                <div key={`${row.period}:${row.name}`} className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 py-2.5">
                  <span className="text-right font-mono text-sm font-medium tabular-nums">
                    {formatStatValue(row.p1, row.unit)}
                  </span>
                  <span className="flex min-w-0 flex-col items-center gap-1 text-center text-xs text-muted-foreground sm:text-sm">
                    <span className="flex flex-wrap items-center justify-center gap-2">
                      {formatPeriod(row.period)} · {row.label}
                      {row.partial ? <Badge variant="outline">部分提供</Badge> : null}
                    </span>
                    {row.stale ? (
                      <span className="text-[11px] sm:text-xs">
                        数据较旧 · {formatAsOf(row.asOf) ?? '观测时间未知'}
                      </span>
                    ) : null}
                  </span>
                  <span className="font-mono text-sm font-medium tabular-nums">
                    {row.p2 === null ? '官方未返回' : formatStatValue(row.p2, row.unit)}
                  </span>
                </div>
              ))}
              {view.missing.map((label) => (
                <p key={label} className="py-1.5 text-xs text-muted-foreground">
                  {label}官方未返回
                </p>
              ))}
            </div>
          </section>
        ))
      )}

      {lastTen.length > 0 ? (
        <section>
          <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            最近 10 分
          </h3>
          <ol className="flex flex-wrap gap-1.5" aria-label="最近 10 分">
            {lastTen.map((point) => (
              <li
                key={point.id}
                className="rounded-md bg-muted/30 px-2 py-1 font-mono text-xs"
                title={`${point.score_after.points[0] ?? ''} - ${point.score_after.points[1] ?? ''}`}
              >
                {shortName(
                  point.winner_player_id === players[0].id ? players[0].name : players[1].name,
                )}
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      <p className="text-xs text-muted-foreground">
        {formattedAsOf
          ? `最近统计观测：${formattedAsOf}；各项时间可能不同`
          : '统计时间官方未返回'}{' '}
        · 缺失能力保持缺失，不猜测
      </p>
    </div>
  )
}
