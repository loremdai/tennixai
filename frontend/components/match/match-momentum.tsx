'use client'

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ReferenceLine,
  XAxis,
} from 'recharts'
import { TrendingUp, Trophy } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardAction, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import type { MatchSnapshotDto } from '@/lib/api/types'
import type { MatchViewModel } from '@/lib/view-models'
import { formatAsOf, toMomentumChart } from '@/lib/view-models'
import { cn } from '@/lib/utils'

import { FutureModule } from './future-module'
import { type MatchHighlight } from './match-data'
import {
  previewMatchMeta,
  previewMomentumData,
  previewRecentPoints,
} from './match-preview-data'
import { MatchPointsTimeline } from './match-points'

const momentumConfig = {
  momentum: {
    label: '近期控制指数',
    color: 'var(--chart-1)',
  },
} satisfies ChartConfig

type MatchMomentumCardProps = {
  match: MatchViewModel
  preview: boolean
  highlight: MatchHighlight
  snapshot?: MatchSnapshotDto | null
}

function formatIndex(value: number): string {
  const rounded = Math.round(value * 10) / 10
  if (rounded === 0) return '0'
  return rounded > 0 ? `+${rounded}` : String(rounded)
}

function leaderName(match: MatchViewModel, playerId: string | null): string {
  return match.players.find((player) => player.id === playerId)?.shortName ?? '双方'
}

function keyPointLabel(point: MatchSnapshotDto['points'][number]): string {
  const flags = [
    point.is_break_point ? '破发点' : null,
    point.is_set_point ? '盘点' : null,
    point.is_match_point ? '赛点' : null,
  ].filter((flag): flag is string => flag !== null)
  return flags.join(' · ')
}

function RecentControlPanel({
  match,
  snapshot,
}: {
  match: MatchViewModel
  snapshot: MatchSnapshotDto
}) {
  const observations = snapshot.momentum
    .slice()
    .sort((a, b) => a.point_sequence - b.point_sequence)
  const latest = observations.at(-1)
  const chart = toMomentumChart(snapshot.momentum, snapshot.points)
  const keyPoints = snapshot.points
    .filter((point) => point.is_break_point || point.is_set_point || point.is_match_point)
    .filter((point) => chart.some((item) => item.sequence === point.sequence))
  const asOf = formatAsOf(snapshot.as_of)

  if (!latest || chart.length === 0) {
    return (
      <p className="rounded-md bg-muted/25 px-3 py-2 text-xs text-muted-foreground">
        近期控制指数尚未计算；需要供应商返回可判定逐分数据后才会展示最近 20 分走势。
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-medium">{leaderName(match, latest.leader_player_id)} {formatIndex(latest.value)}</p>
          <p className="text-xs text-muted-foreground">
            最近 {chart.length} 分 · {asOf ? `更新于 ${asOf}` : '更新时间官方未返回'}
          </p>
        </div>
        {latest.is_provisional ? <Badge variant="outline">暂定走势</Badge> : <Badge variant="secondary">已校准</Badge>}
      </div>

      <ChartContainer config={momentumConfig} className="h-44 w-full" aria-label="近期控制指数图表">
        <LineChart accessibilityLayer data={chart} margin={{ left: 8, right: 8, top: 12, bottom: 0 }}>
          <CartesianGrid vertical={false} strokeDasharray="3 6" />
          <XAxis
            dataKey="sequence"
            type="number"
            domain={['dataMin', 'dataMax']}
            tickLine={false}
            axisLine={false}
            tickMargin={10}
            tickFormatter={(value: number) => `${value}`}
          />
          <ReferenceLine y={0} stroke="var(--border)" />
          <ChartTooltip
            content={<ChartTooltipContent hideLabel />}
            formatter={(value) => [formatIndex(Number(value)), '控制指数']}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke="var(--color-momentum)"
            strokeWidth={2.5}
            dot={false}
            activeDot={{ r: 4 }}
          />
          {chart.filter((item) => item.isKeyPoint).map((item) => (
            <ReferenceDot
              key={item.sequence}
              x={item.sequence}
              y={item.value}
              r={4}
              fill="var(--color-momentum)"
              stroke="var(--background)"
              strokeWidth={2}
            />
          ))}
        </LineChart>
      </ChartContainer>

      {latest.is_provisional ? (
        <p className="text-xs text-muted-foreground">样本较少，当前为暂定走势；至少 6 个可确定分后再作为稳定参考。</p>
      ) : null}

      <ol className="sr-only" aria-label="近期控制指数观测">
        {chart.map((item) => (
          <li key={item.sequence}>第 {item.sequence} 分：{formatIndex(item.value)}</li>
        ))}
      </ol>

      {keyPoints.length > 0 ? (
        <section aria-label="关键分标记">
          <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">关键分标记</h3>
          <ul className="flex flex-wrap gap-2 text-xs text-muted-foreground">
            {keyPoints.map((point) => (
              <li key={point.id} className="rounded-md bg-muted/30 px-2 py-1">
                第 {point.sequence} 分 · {keyPointLabel(point)}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  )
}

export function MatchMomentumCard({
  match,
  preview,
  highlight,
  snapshot,
}: MatchMomentumCardProps) {
  const visualStatus = match.visualStatus
  const liveSnapshot = !preview && visualStatus !== 'upcoming' ? snapshot ?? null : null

  return (
    <Card
      id="momentum"
      className={cn(
        'scroll-mt-24 transition-[box-shadow,background-color]',
        highlight === 'momentum' && 'bg-primary/5 ring-2 ring-primary/60',
      )}
    >
      <CardHeader>
        <CardTitle><h2>{visualStatus === 'finished' ? '比赛总结' : '逐分与动量'}</h2></CardTitle>
        <p className="text-sm text-muted-foreground">
          {visualStatus === 'finished' ? '决胜盘的关键转折' : '最近 20 分的比赛控制指数'}
        </p>
        <CardAction>
          {preview ? (
            visualStatus === 'upcoming' ? (
              <Badge variant="outline">P2</Badge>
            ) : visualStatus === 'live' ? (
              <Badge variant="secondary">
                <TrendingUp data-icon="inline-start" aria-hidden="true" />
                Sinner +14
              </Badge>
            ) : (
              <Badge variant="secondary">赛后</Badge>
            )
          ) : (
            <Badge variant="outline">{liveSnapshot ? 'P2 实时' : 'P2 数据暂不可用'}</Badge>
          )}
        </CardAction>
      </CardHeader>
      <CardContent>
        {liveSnapshot ? (
          <div className="flex flex-col gap-5">
            <MatchPointsTimeline points={liveSnapshot.points} players={liveSnapshot.match.players} />
            <RecentControlPanel match={match} snapshot={liveSnapshot} />
          </div>
        ) : match.visualStatus === 'upcoming' ? (
          <FutureModule
            phase="P2"
            title="动量时间线将在直播中展开"
            description="关键破发、盘点与连续得分会与比赛走势同步标注。"
          />
        ) : preview ? (
          visualStatus === 'finished' ? (
            <div className="flex flex-col gap-4 rounded-lg bg-muted/25 p-4">
              <div className="flex items-start gap-3">
                <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-secondary text-primary">
                  <Trophy aria-hidden="true" className="size-4" />
                </div>
                <div>
                  <h3 className="font-semibold">Sinner 在决胜盘掌控关键分</h3>
                  <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                    双方各赢一盘后，Sinner 在第三盘提升一发质量，并通过一次关键破发建立领先，最终以 6–3 收下比赛。
                  </p>
                </div>
              </div>
              <dl className="grid grid-cols-2 gap-3 border-t pt-4 sm:grid-cols-3">
                <div><dt className="text-xs text-muted-foreground">胜者</dt><dd className="mt-1 font-medium">Jannik Sinner</dd></div>
                <div><dt className="text-xs text-muted-foreground">时长</dt><dd className="mt-1 font-medium">{previewMatchMeta.finalDuration}</dd></div>
                <div><dt className="text-xs text-muted-foreground">决胜盘</dt><dd className="mt-1 font-mono font-semibold text-primary">6–3</dd></div>
              </dl>
            </div>
          ) : (
            <div className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(16rem,0.75fr)]">
              <div className="min-w-0">
                <ChartContainer config={momentumConfig} className="h-44 w-full">
                  <LineChart accessibilityLayer data={previewMomentumData} margin={{ left: 8, right: 8, top: 12, bottom: 0 }}>
                    <CartesianGrid vertical={false} strokeDasharray="3 6" />
                    <XAxis dataKey="point" tickLine={false} axisLine={false} tickMargin={10} interval="preserveStartEnd" />
                    <ReferenceLine y={0} stroke="var(--border)" />
                    <ChartTooltip content={<ChartTooltipContent hideLabel />} />
                    <Line type="monotone" dataKey="momentum" stroke="var(--color-momentum)" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
                  </LineChart>
                </ChartContainer>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  Sinner 在最近 7 个短回合中赢下 5 分，比赛控制指数上升至 +14。
                </p>
              </div>

              <ol className="flex flex-col divide-y" aria-label="最近比赛事件">
                {previewRecentPoints.map((point) => (
                  <li key={`${point.score}-${point.detail}`} className="flex items-start gap-3 py-2.5 first:pt-0 last:pb-0">
                    <span className="mt-1 size-2 shrink-0 rounded-full bg-primary" aria-hidden="true" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">{point.player}</span>
                        <span className="font-mono text-sm text-muted-foreground">{point.score}</span>
                      </div>
                      <p className="mt-1 text-sm text-muted-foreground">{point.detail}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          )
        ) : (
          <FutureModule
            phase="P2"
            title="P2 数据暂不可用"
            description="逐分事件与动量指数属于 P2 实时比赛智能；P1 不提供该数据。"
          />
        )}
      </CardContent>
    </Card>
  )
}
