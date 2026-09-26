'use client'

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceDot,
  ReferenceLine,
  XAxis,
  YAxis,
} from 'recharts'
import { Trophy } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { PlayerName } from '@/components/player-name'
import { Card, CardAction, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import type { MatchSnapshotDto } from '@/lib/api/types'
import type { MatchViewModel } from '@/lib/view-models'
import type { MomentumChartPoint } from '@/lib/view-models'
import { formatAsOf, toMomentumChart } from '@/lib/view-models'
import { cn } from '@/lib/utils'

import { FutureModule } from './future-module'
import { type MatchHighlight } from './match-data'
import {
  previewMatchMeta,
  previewMomentumData,
  previewPlayers,
  previewRecentPoints,
} from './match-preview-data'
import { MatchPointsTimeline } from './match-points'

const momentumConfig = {
  momentum: {
    label: '近期走势指数',
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
  const playerIds = new Set(match.players.map((player) => player.id))
  const pointBySequence = new Map(snapshot.points.map((point) => [point.sequence, point]))
  const observations = snapshot.momentum
    .filter((item) => playerIds.has(pointBySequence.get(item.point_sequence)?.winner_player_id ?? ''))
    .slice()
    .sort((a, b) => a.point_sequence - b.point_sequence)
  const latest = observations.at(-1)
  const chart = toMomentumChart(observations, snapshot.points)
  const confirmed = chart.filter(
    (item): item is MomentumChartPoint & { value: number } => item.value !== null,
  )
  const keyPoints = snapshot.points
    .filter((point) => point.is_break_point || point.is_set_point || point.is_match_point)
    .filter((point) => confirmed.some((item) => item.sequence === point.sequence))

  if (!latest || chart.length === 0) {
    const description = snapshot.points.length === 0
      ? '暂时没有可用的逐分记录，比赛走势会在数据到达后显示。'
      : snapshot.points.some((point) => playerIds.has(point.winner_player_id ?? ''))
        ? '已有得分记录，走势尚未生成。'
        : '已有逐分记录，但得分者均无法确认，暂不能绘制走势。'
    return (
      <p className="rounded-md bg-muted/25 px-3 py-2 text-xs text-muted-foreground">
        {description}
      </p>
    )
  }

  const asOf = formatAsOf(latest.as_of)
  const [positivePlayer, negativePlayer] = match.players
  const displayedIndex = Math.round(latest.value * 10) / 10
  const leader = displayedIndex > 0 ? positivePlayer : displayedIndex < 0 ? negativePlayer : null
  const insufficient = latest.is_provisional || confirmed.length < 6
  const maxMagnitude = Math.max(...confirmed.map((item) => Math.abs(item.value)))
  const extent = Math.min(100, Math.max(20, Math.ceil(maxMagnitude / 10) * 10))
  const hasGap = chart.some((item) => item.value === null)
  const trailingPoints = snapshot.points.filter((point) => point.sequence > latest.point_sequence)
  const trailingWinnersUnknown = trailingPoints.every((point) => !playerIds.has(point.winner_player_id ?? ''))

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <h3 className="flex flex-wrap items-center gap-x-1 text-base font-semibold">
            {insufficient ? (
              '可确认得分不足，暂不判断走势。'
            ) : leader ? (
              <>
                <span>近期走势偏向</span>
                <PlayerName
                  name={leader.name}
                  localizedName={leader.nameZh}
                  primaryClassName="whitespace-normal break-words text-base"
                  secondaryClassName="whitespace-normal break-words"
                />
              </>
            ) : (
              '近期走势接近均衡'
            )}
          </h3>
          <p className="text-xs text-muted-foreground">最近 {confirmed.length} 个已确认得分</p>
          <p className="text-xs text-muted-foreground">
            {asOf ? `走势截至 ${asOf}` : '走势记录时间暂不可用'}
          </p>
        </div>
        {insufficient ? <Badge variant="outline">样本较少</Badge> : (
          <span className="rounded-full border border-border px-2.5 py-1 text-xs tabular-nums text-muted-foreground">
            走势指数 {formatIndex(latest.value)}（不是胜率）
          </span>
        )}
      </div>

      {insufficient ? null : (
        <div className="min-w-0 rounded-lg border border-border/70 bg-muted/10 px-3 py-3">
          <div className="flex items-start justify-between gap-2 text-xs">
            <div className="flex min-w-0 items-start gap-1 text-primary">
              <span className="shrink-0">上方：</span>
              <PlayerName
                name={positivePlayer.name}
                localizedName={positivePlayer.nameZh}
                primaryClassName="whitespace-normal break-words"
                secondaryClassName="whitespace-normal break-words"
              />
            </div>
            <span className="tabular-nums text-muted-foreground">+{extent}</span>
          </div>
          <ChartContainer
            config={momentumConfig}
            className="h-52 w-full min-w-0"
            aria-label={`近期比赛走势：上方${positivePlayer.name}，下方${negativePlayer.name}，0为相对均衡`}
          >
            <LineChart accessibilityLayer data={chart} margin={{ left: 24, right: 24, top: 8, bottom: 0 }}>
              <ReferenceArea y1={0} y2={extent} fill="var(--primary)" fillOpacity={0.05} stroke="none" />
              <ReferenceArea y1={-extent} y2={0} fill="var(--chart-2)" fillOpacity={0.06} stroke="none" />
              <CartesianGrid vertical={false} strokeDasharray="3 6" />
              <YAxis hide domain={[-extent, extent]} ticks={[-extent, 0, extent]} />
              <XAxis
                dataKey="sequence"
                type="number"
                domain={['dataMin', 'dataMax']}
                ticks={[chart[0].sequence, confirmed.at(-1)!.sequence]}
                interval={0}
                tickLine={false}
                axisLine={false}
                tickMargin={10}
                tickFormatter={(value: number) => `第${value}分`}
              />
              <ReferenceLine y={0} stroke="var(--foreground)" strokeOpacity={0.7} strokeWidth={1.5} />
              <ChartTooltip
                content={(
                  <ChartTooltipContent
                    hideIndicator
                    labelFormatter={(_label, payload) => {
                      const item = payload[0]?.payload as MomentumChartPoint | undefined
                      return item?.value == null ? null : `第 ${item.sequence} 分`
                    }}
                    formatter={(value, _name, item) => {
                      const chartPoint = item.payload as MomentumChartPoint
                      const winner = match.players.find((player) => player.id === chartPoint.winnerPlayerId)
                      const point = pointBySequence.get(chartPoint.sequence)
                      return (
                        <div className="grid gap-1 leading-snug">
                          <span>走势指数 {formatIndex(Number(value))}</span>
                          <span>本分得分者：{winner ? `${winner.name}${winner.nameZh ? ` · ${winner.nameZh}` : ''}` : '未确认'}</span>
                          {point && keyPointLabel(point) ? <span>{keyPointLabel(point)}</span> : null}
                        </div>
                      )
                    }}
                  />
                )}
              />
              <Line
                type="linear"
                dataKey="value"
                stroke="var(--color-momentum)"
                strokeWidth={2.5}
                dot={{ r: 2, fill: 'var(--color-momentum)', strokeWidth: 0 }}
                activeDot={{ r: 4 }}
                connectNulls={false}
                isAnimationActive={false}
              />
              {confirmed.filter((item) => item.isKeyPoint).map((item) => (
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
              <ReferenceDot
                x={confirmed.at(-1)!.sequence}
                y={confirmed.at(-1)!.value}
                r={5}
                fill="var(--color-momentum)"
                stroke="var(--background)"
                strokeWidth={2}
              />
            </LineChart>
          </ChartContainer>
          <div className="flex items-end justify-between gap-2 text-xs">
            <div className="flex min-w-0 items-start gap-1 text-muted-foreground">
              <span className="shrink-0">下方：</span>
              <PlayerName
                name={negativePlayer.name}
                localizedName={negativePlayer.nameZh}
                primaryClassName="whitespace-normal break-words"
                secondaryClassName="whitespace-normal break-words"
              />
            </div>
            <span className="tabular-nums text-muted-foreground">-{extent}</span>
          </div>
          <p className="mt-2 border-t border-border/60 pt-2 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">0 · 相对均衡</span>；曲线越过中线表示近期走势转向另一方。
          </p>
        </div>
      )}

      {hasGap && !insufficient ? (
        <p className="text-xs text-muted-foreground">有些得分未纳入走势，曲线在缺口处断开。</p>
      ) : null}
      {trailingPoints.length > 0 ? (
        <p className="text-xs text-muted-foreground">
          {trailingWinnersUnknown
            ? `之后还有 ${trailingPoints.length} 分得分者无法确认，走势停留在第 ${latest.point_sequence} 分。`
            : `之后还有 ${trailingPoints.length} 分尚未计入走势，走势停留在第 ${latest.point_sequence} 分。`}
        </p>
      ) : null}
      <p className="text-xs text-muted-foreground">这只反映最近得分走势，不等于当前比分或获胜概率。</p>

      <ol className="sr-only" aria-label="近期比赛走势观测">
        {confirmed.map((item) => {
          const winner = match.players.find((player) => player.id === item.winnerPlayerId)
          return (
            <li key={item.sequence}>
              第 {item.sequence} 分：走势指数 {formatIndex(item.value)}；本分得分者 {winner?.name ?? '未确认'}
            </li>
          )
        })}
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
        <CardTitle><h2>{visualStatus === 'finished' ? '比赛总结' : '得分走势与关键分'}</h2></CardTitle>
        <p className="text-sm text-muted-foreground">
          {visualStatus === 'finished' ? '关键分与比赛走势' : '查看近期得分走势与关键分'}
        </p>
        <CardAction>
          {preview ? (
            <Badge variant="outline">演示数据</Badge>
          ) : (
            liveSnapshot ? <Badge variant="outline">实时数据</Badge> : null
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
            title="逐分记录将在比赛开始后显示"
            description="如有可用数据，这里会标出破发点、盘点和赛点。"
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
                <div>
                  <dt className="text-xs text-muted-foreground">胜者</dt>
                  <dd className="mt-1 font-medium">
                    <PlayerName name={previewPlayers[0].name} localizedName={previewPlayers[0].nameZh} />
                  </dd>
                </div>
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
                  Sinner 最近 7 个短回合中赢下 5 分，近期走势指数升至 +14。
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
            title="暂无逐分与走势数据"
            description="本场比赛暂未提供逐分记录，因此无法展示近期走势。"
          />
        )}
      </CardContent>
    </Card>
  )
}
