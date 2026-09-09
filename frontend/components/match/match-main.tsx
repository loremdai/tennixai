'use client'

import type { LucideIcon } from 'lucide-react'
import {
  Activity,
  BrainCircuit,
  CalendarClock,
  CircleDot,
  Clock3,
  Gauge,
  Layers3,
  MapPin,
  Radio,
  Sparkles,
  Trophy,
  TrendingUp,
} from 'lucide-react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  XAxis,
} from 'recharts'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import { Separator } from '@/components/ui/separator'
import type { MatchSnapshotDto } from '@/lib/api/types'
import type { MatchViewModel } from '@/lib/view-models'
import { formatAsOf } from '@/lib/view-models'
import { cn } from '@/lib/utils'

import { FutureModule } from './future-module'
import { setLabel, type MatchHighlight, type MatchStatus } from './match-data'
import { MatchPointsTimeline } from './match-points'
import {
  getPreviewPlayer,
  previewFinishedScore,
  previewLiveScore,
  previewMatchMeta,
  previewMatchStats,
  previewMomentumData,
  previewPromptsByStatus,
  previewRecentPoints,
} from './match-preview-data'
import { MatchStatisticsCard } from './match-statistics'

type MainColumnProps = {
  match: MatchViewModel
  preview: boolean
  highlight: MatchHighlight
  onPromptSelect: (prompt: string) => void
  snapshot?: MatchSnapshotDto | null
}

const momentumConfig = {
  momentum: {
    label: 'Sinner 动量指数',
    color: 'var(--chart-1)',
  },
} satisfies ChartConfig

const highlightedServeStats = new Set(['一发成功率', '一发得分率', 'ACE 球'])

const promptsByVisualStatus: Record<MatchViewModel['visualStatus'], string[]> = {
  upcoming: ['这场比赛几点开始？', '这是什么赛事？', '现在进行到哪一轮？', '比赛是什么场地？'],
  live: ['现在谁在发球？', '当前比分是多少？'],
  finished: ['谁赢了？', '最终比分是多少？'],
  unavailable: ['这场比赛目前状态如何？'],
}

function OverviewItem({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon
  label: string
  value: string
}) {
  return (
    <div className="flex min-w-0 items-start gap-3">
      <Icon aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
      <div className="min-w-0">
        <dt className="text-sm text-muted-foreground">{label}</dt>
        <dd className="mt-1 break-words text-sm font-medium">{value}</dd>
      </div>
    </div>
  )
}

function OverviewCard({ match, preview }: Pick<MainColumnProps, 'match' | 'preview'>) {
  const statusValue =
    match.visualStatus === 'upcoming'
      ? '即将开始'
      : match.visualStatus === 'live'
        ? '比赛进行中'
        : match.visualStatus === 'finished'
          ? '已完赛'
          : '状态待确认'

  const items = preview
    ? [
        { icon: Layers3, label: '赛事 / 轮次', value: `${previewMatchMeta.tournament} · ${previewMatchMeta.round}` },
        { icon: MapPin, label: '地点', value: `${previewMatchMeta.venue} · ${previewMatchMeta.location}` },
        { icon: CalendarClock, label: '开赛时间', value: `${previewMatchMeta.scheduledDate} · ${previewMatchMeta.scheduledTime}` },
        { icon: CircleDot, label: '球场', value: match.visualStatus === 'upcoming' ? '暂未公布' : previewMatchMeta.court },
        { icon: Gauge, label: '场地', value: previewMatchMeta.surface },
        { icon: Clock3, label: '赛制', value: previewMatchMeta.format },
        {
          icon: match.visualStatus === 'finished' ? Trophy : Radio,
          label: '比赛状态',
          value: preview
            ? match.visualStatus === 'upcoming'
              ? '即将开始'
              : match.visualStatus === 'live'
                ? '第三盘进行中'
                : '已完赛'
            : statusValue,
        },
      ]
    : [
        { icon: Layers3, label: '赛事 / 轮次', value: `${match.tournament} · ${match.round}` },
        { icon: CalendarClock, label: '开赛时间', value: `${match.scheduledDate} · ${match.scheduledTime}（${match.timezoneLabel}）` },
        { icon: Gauge, label: '场地', value: match.surface },
        { icon: CircleDot, label: '环境', value: match.indoorLabel },
        { icon: Clock3, label: '赛制', value: match.format },
        { icon: match.visualStatus === 'finished' ? Trophy : Radio, label: '比赛状态', value: statusValue },
        { icon: Activity, label: '数据新鲜度', value: match.freshnessLabel },
      ]

  return (
    <Card>
      <CardHeader>
        <CardTitle><h2>比赛概览</h2></CardTitle>
        <p className="text-sm text-muted-foreground">赛事上下文与本地时间</p>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {items.map((item) => <OverviewItem key={item.label} {...item} />)}
        </dl>
      </CardContent>
    </Card>
  )
}

type ScoreRowView = {
  playerId: string
  shortName: string
  sets: Array<number | null>
  points?: string | null
  serving?: boolean
  winner?: boolean
}

function ScoreTable({ rows, showPoints }: { rows: [ScoreRowView, ScoreRowView]; showPoints: boolean }) {
  const setCount = rows[0].sets.length
  return (
    <table className="w-full table-fixed" aria-label={showPoints ? '实时详细比分' : '最终详细比分'}>
      <caption className="sr-only">
        {showPoints ? '本场比赛逐盘比分与当前局分' : '本场比赛最终逐盘比分'}
      </caption>
      <thead>
        <tr className="text-xs text-muted-foreground sm:text-sm">
          <th scope="col" className="w-20 pb-3 text-left font-normal">球员</th>
          {rows[0].sets.map((_, index) => (
            <th key={index} scope="col" className={cn('pb-3 font-normal', index === setCount - 1 && 'text-primary')}>
              {setLabel(index)}
            </th>
          ))}
          {showPoints ? <th scope="col" className="pb-3 font-normal">当前局</th> : null}
        </tr>
      </thead>
      <tbody className="font-mono text-lg font-semibold tabular-nums">
        {rows.map((row) => (
          <tr key={row.playerId} className="border-t">
            <th scope="row" className="py-3 text-left font-sans text-sm font-medium">
              <span className="flex items-center gap-2">
                {row.serving ? <span className="size-2 rounded-full bg-primary" aria-label="发球方" /> : null}
                {row.shortName}
              </span>
            </th>
            {row.sets.map((set, index) => (
              <td key={`${row.playerId}-${index}`} className={cn('text-center', index === setCount - 1 && 'text-primary')}>
                {set ?? '-'}
              </td>
            ))}
            {showPoints ? <td className="text-center text-xl">{row.points ?? ''}</td> : null}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function rowsFromMatch(match: MatchViewModel): [ScoreRowView, ScoreRowView] | null {
  const score = match.score
  if (!score) return null
  return [0, 1].map((index) => ({
    playerId: match.players[index].id,
    shortName: match.players[index].shortName,
    sets: score.sets.map((set) =>
      index === 0 ? set.player1_games : set.player2_games,
    ),
    points: score.points[index],
    serving: match.serverPlayerId === match.players[index].id,
    winner: match.winnerPlayerId === match.players[index].id,
  })) as [ScoreRowView, ScoreRowView]
}

function ScoreProgressCard({ match, preview, highlight }: Pick<MainColumnProps, 'match' | 'preview' | 'highlight'>) {
  const visualStatus = match.visualStatus
  const rows = preview
    ? (visualStatus === 'finished'
        ? previewFinishedScore.rows.map((row) => {
            const player = getPreviewPlayer(row.playerId)
            return { playerId: row.playerId, shortName: player.shortName, sets: row.sets, points: row.points, serving: row.serving, winner: row.winner }
          }) as [ScoreRowView, ScoreRowView]
        : previewLiveScore.rows.map((row) => {
            const player = getPreviewPlayer(row.playerId)
            return { playerId: row.playerId, shortName: player.shortName, sets: row.sets, points: row.points, serving: row.serving, winner: row.winner }
          }) as [ScoreRowView, ScoreRowView])
    : rowsFromMatch(match)

  return (
    <Card
      id="score-progress"
      className={cn(
        'scroll-mt-24 transition-[box-shadow,background-color]',
        highlight === 'score' && 'bg-primary/5 ring-2 ring-primary/60',
      )}
    >
      <CardHeader>
        <CardTitle><h2>比分与比赛进程</h2></CardTitle>
        <p className="text-sm text-muted-foreground">
          {visualStatus === 'finished' ? '最终逐盘比分与比赛结果' : '逐盘比分、当前局分与发球权'}
        </p>
        <CardAction>
          <Badge variant={visualStatus === 'upcoming' ? 'outline' : 'secondary'}>
            {visualStatus === 'upcoming'
              ? '等待开赛'
              : visualStatus === 'live'
                ? `第 ${match.score?.sets.length ?? '-'} 盘`
                : visualStatus === 'finished'
                  ? '已完赛'
                  : '状态待确认'}
          </Badge>
        </CardAction>
      </CardHeader>
      <CardContent>
        {visualStatus === 'upcoming' || visualStatus === 'unavailable' || !rows ? (
          <FutureModule
            phase="P2"
            title="实时比分将在开赛后自动出现"
            description="无需切换页面；盘分、局分、发球方与抢七状态会在此模块内实时更新。"
          />
        ) : visualStatus === 'live' ? (
          <div className="flex flex-col gap-5">
            <ScoreTable rows={rows} showPoints />
            <div className="grid grid-cols-3 items-center rounded-lg bg-muted/30 p-4 text-center">
              <div>
                <p className="font-mono text-2xl font-semibold">{rows[0].points ?? '–'}</p>
                <p className="text-sm text-muted-foreground">{rows[0].shortName}</p>
              </div>
              <div className="flex flex-col items-center gap-1">
                <Badge>发球局</Badge>
                <span className="text-sm text-muted-foreground">
                  {preview ? '4–5 · 0 个破发点' : match.freshnessLabel}
                </span>
              </div>
              <div>
                <p className="font-mono text-2xl font-semibold">{rows[1].points ?? '–'}</p>
                <p className="text-sm text-muted-foreground">{rows[1].shortName}</p>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-5">
            <ScoreTable rows={rows} showPoints={false} />
            <div className="flex flex-col gap-2 rounded-lg bg-muted/30 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-semibold">
                  {match.players.find((player) => player.id === match.winnerPlayerId)?.name ?? '比赛已结束'}
                  {match.winnerPlayerId ? ' 获胜' : ''}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  最终比分 {rows[0].sets.map((games, index) => `${games ?? '-'}–${rows[1].sets[index] ?? '-'}`).join('、')}
                </p>
              </div>
              <Badge variant="secondary">{preview ? previewMatchMeta.finalDuration : match.freshnessLabel}</Badge>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function ComparisonRow({
  label,
  sinner,
  alcaraz,
  sinnerShare,
  highlighted,
}: { label: string; sinner: string; alcaraz: string; sinnerShare: number; highlighted: boolean }) {
  const leftWidth = Math.max(16, sinnerShare)
  const rightWidth = Math.max(16, 100 - sinnerShare)

  return (
    <div className={cn('grid grid-cols-[2.75rem_1fr_5.75rem_1fr_2.75rem] items-center gap-2 rounded-md py-2.5 transition-colors', highlighted && 'bg-primary/10 px-2')}>
      <span className="text-right font-mono text-sm font-medium tabular-nums">{sinner}</span>
      <div className="flex h-1.5 justify-end overflow-hidden rounded-full bg-muted" aria-hidden="true">
        <span className="h-full rounded-full bg-primary" style={{ width: `${leftWidth}%` }} />
      </div>
      <span className="text-center text-xs text-muted-foreground sm:text-sm">{label}</span>
      <div className="flex h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden="true">
        <span className="h-full rounded-full bg-foreground/50" style={{ width: `${rightWidth}%` }} />
      </div>
      <span className="font-mono text-sm font-medium tabular-nums">{alcaraz}</span>
    </div>
  )
}

function StatsCard({ match, preview, highlight, snapshot }: Pick<MainColumnProps, 'match' | 'preview' | 'highlight' | 'snapshot'>) {
  const isHighlighted = highlight === 'serve-stats'
  const liveSnapshot = !preview && match.visualStatus !== 'upcoming' ? snapshot ?? null : null

  return (
    <Card
      id="technical-stats"
      className={cn(
        'scroll-mt-24 transition-[box-shadow,background-color]',
        isHighlighted && 'bg-primary/5 ring-2 ring-primary/60',
      )}
      aria-live="polite"
    >
      <CardHeader>
        <CardTitle><h2>技术统计</h2></CardTitle>
        <p className="text-sm text-muted-foreground">
          {match.visualStatus === 'finished' ? '赛后技术表现对比' : '实时技术表现对比'}
        </p>
        <CardAction>
          <Badge variant="outline">
            {preview
              ? match.visualStatus === 'finished'
                ? 'P2 赛后'
                : 'P2 预览'
              : liveSnapshot
                ? 'P2 实时'
                : 'P2 数据暂不可用'}
          </Badge>
        </CardAction>
      </CardHeader>
      <CardContent>
        {liveSnapshot ? (
          <MatchStatisticsCard
            statistics={liveSnapshot.statistics}
            points={liveSnapshot.points}
            players={liveSnapshot.match.players}
            asOf={formatAsOf(liveSnapshot.as_of)}
          />
        ) : match.visualStatus === 'upcoming' ? (
          <FutureModule
            phase="P2"
            title="技术统计等待实时数据"
            description="开赛后将呈现发球、接发与破发效率的逐项对比。"
          />
        ) : preview ? (
          <div>
            <div className="grid grid-cols-2 border-b pb-3 text-sm font-medium">
              <span>{match.players[0].shortName}</span>
              <span className="text-right">{match.players[1].shortName}</span>
            </div>
            <div className="divide-y">
              {previewMatchStats.map((stat) => (
                <ComparisonRow
                  key={stat.label}
                  label={stat.label}
                  sinner={stat.sinner}
                  alcaraz={stat.alcaraz}
                  sinnerShare={stat.sinnerShare}
                  highlighted={isHighlighted && highlightedServeStats.has(stat.label)}
                />
              ))}
            </div>
          </div>
        ) : (
          <FutureModule
            phase="P2"
            title="P2 数据暂不可用"
            description="技术统计属于 P2 实时比赛智能；P1 只提供赛程、比分、发球方等结构化事实。"
          />
        )}
      </CardContent>
    </Card>
  )
}

function MomentumCard({ match, preview, highlight, snapshot }: Pick<MainColumnProps, 'match' | 'preview' | 'highlight' | 'snapshot'>) {
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
            {liveSnapshot.momentum.length === 0 ? (
              <p className="rounded-md bg-muted/25 px-3 py-2 text-xs text-muted-foreground">
                近期控制指数暂未提供；校准完成后将在此展示最近 20 分走势，缺失能力保持缺失。
              </p>
            ) : null}
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

function InsightRow({
  icon: Icon,
  eyebrow,
  title,
  body,
}: {
  icon: LucideIcon
  eyebrow: string
  title: string
  body: string
}) {
  return (
    <article className="flex items-start gap-3 py-4 first:pt-0 last:pb-0">
      <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-secondary text-primary">
        <Icon aria-hidden="true" className="size-4" />
      </div>
      <div className="min-w-0">
        <p className="text-sm font-medium text-primary">{eyebrow}</p>
        <h3 className="mt-1 text-pretty text-base font-semibold">{title}</h3>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{body}</p>
      </div>
    </article>
  )
}

function AIInsightsCard({ match, preview, onPromptSelect }: Pick<MainColumnProps, 'match' | 'preview' | 'onPromptSelect'>) {
  const visualStatus = match.visualStatus
  const previewStatus: MatchStatus = visualStatus === 'unavailable' ? 'upcoming' : visualStatus
  const prompts = preview ? previewPromptsByStatus[previewStatus] : promptsByVisualStatus[visualStatus]

  const previewContent =
    visualStatus === 'upcoming'
      ? {
          title: '赛前问题建议',
          description: '基于当前比赛的赛程与对阵背景',
          insights: [
            {
              icon: CalendarClock,
              eyebrow: '赛程确认',
              title: '本场预计于今天 20:30 开始',
              body: '地点是都灵 Inalpi Arena；具体球场将在开赛前公布。',
            },
            {
              icon: Layers3,
              eyebrow: '对阵背景',
              title: '两位球员的硬地对局长期接近',
              body: '近 6 次硬地交手各胜 3 场，决胜盘的一发稳定性通常是关键变量。',
            },
          ],
        }
      : visualStatus === 'live'
        ? {
            title: '实时问题建议',
            description: '将当前比分连接到可解释的比赛数据',
            insights: [
              {
                icon: Gauge,
                eyebrow: '发球质量',
                title: 'Sinner 的一发正在拉开差距',
                body: '一发成功率 68%，一发得分率 79%，并已发出 8 记 ACE。',
              },
              {
                icon: Activity,
                eyebrow: '动量变化',
                title: '主动权正轻微转向 Sinner',
                body: '他在最近 7 个短回合中赢下 5 分，但仍需要守住当前发球局。',
              },
            ],
          }
        : {
            title: '赛后问题建议',
            description: '从最终比分提取关键结论',
            insights: [
              {
                icon: Trophy,
                eyebrow: '比赛结果',
                title: 'Sinner 以三盘赢下半决赛',
                body: '最终比分为 6–4、4–6、6–3，比赛持续 2 小时 28 分。',
              },
              {
                icon: BrainCircuit,
                eyebrow: '比赛摘要',
                title: '更稳定的一发决定了决胜盘',
                body: 'Sinner 在第三盘提高发球质量，并通过一次关键破发锁定优势。',
              },
            ],
          }

  return (
    <Card>
      <CardHeader>
        <CardTitle><h2>{preview ? previewContent.title : '本场比赛问题建议'}</h2></CardTitle>
        <p className="text-sm text-muted-foreground">
          {preview ? previewContent.description : '直接询问时间、比分、发球与赛事信息'}
        </p>
        <CardAction>
          <Badge>
            <Sparkles data-icon="inline-start" aria-hidden="true" />
            AI
          </Badge>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {preview ? (
          <div className="divide-y">
            {previewContent.insights.map((insight) => <InsightRow key={insight.title} {...insight} />)}
          </div>
        ) : null}
        {preview ? <Separator /> : null}
        <div className="flex flex-wrap gap-2" aria-label="本场比赛示例问题">
          {prompts.map((prompt) => (
            <Button key={prompt} variant="outline" size="sm" onClick={() => onPromptSelect(prompt)}>
              {prompt}
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

export function MatchMainColumn({ match, preview, highlight, onPromptSelect, snapshot }: MainColumnProps) {
  return (
    <div className="flex min-w-0 flex-col gap-4">
      <OverviewCard match={match} preview={preview} />
      <ScoreProgressCard match={match} preview={preview} highlight={highlight} />
      <StatsCard match={match} preview={preview} highlight={highlight} snapshot={snapshot} />
      <MomentumCard match={match} preview={preview} highlight={highlight} snapshot={snapshot} />
      <AIInsightsCard match={match} preview={preview} onPromptSelect={onPromptSelect} />
    </div>
  )
}

export type { MatchStatus }
