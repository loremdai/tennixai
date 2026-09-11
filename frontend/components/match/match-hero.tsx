import {
  Clock3,
  Radio,
  RefreshCw,
  Sparkles,
  Trophy,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardAction,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import type { MatchScoreDto } from '@/lib/api/types'
import type { MatchViewModel } from '@/lib/view-models'
import { cn } from '@/lib/utils'

import type { MatchHighlight } from './match-data'
import { setLabel } from './match-data'
import {
  getPreviewPlayer,
  previewMatchMeta,
  type PreviewPlayer,
} from './match-preview-data'

type MatchHeroProps = {
  match: MatchViewModel
  highlight: MatchHighlight
  onAsk: () => void
  onRefresh?: () => void
  preview?: boolean
}

function PlayerSummary({
  player,
  previewPlayer,
  side,
  visualStatus,
  isServing,
  isWinner,
  highlight,
}: {
  player: MatchViewModel['players'][number]
  previewPlayer: PreviewPlayer | null
  side: 'left' | 'right'
  visualStatus: MatchViewModel['visualStatus']
  isServing: boolean
  isWinner: boolean
  highlight: MatchHighlight
}) {
  return (
    <div
      className={cn(
        'flex min-w-0 flex-col gap-3',
        side === 'right' ? 'items-end text-right' : 'items-start text-left',
      )}
    >
      <div className={cn('flex flex-wrap items-center gap-2', side === 'right' && 'justify-end')}>
        {previewPlayer ? (
          <img
            src={previewPlayer.flagUrl}
            alt={`${previewPlayer.country}国旗`}
            width={20}
            height={14}
            loading="eager"
            fetchPriority="high"
            className="h-3.5 w-5 rounded-sm object-cover ring-1 ring-border"
          />
        ) : null}
        <span className="font-mono text-xs text-muted-foreground">{player.countryCode}</span>
        {player.ranking !== null ? (
          <Badge variant="outline">{previewPlayer ? `${previewPlayer.seed} 号种子` : `#${player.ranking}`}</Badge>
        ) : (
          <Badge variant="outline">官方未返回排名</Badge>
        )}
      </div>

      <div className="min-w-0">
        <p className="text-pretty text-lg font-semibold leading-tight tracking-tight sm:text-2xl lg:text-3xl">
          {player.name}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          {player.ranking !== null ? `世界排名 #${player.ranking}` : '世界排名官方未返回'}
        </p>
      </div>

      {visualStatus === 'upcoming' ? (
        <span className="text-sm text-muted-foreground">赛前档案</span>
      ) : visualStatus === 'finished' ? (
        isWinner ? (
          <Badge variant="secondary">
            <Trophy data-icon="inline-start" aria-hidden="true" />
            胜者
          </Badge>
        ) : (
          <span className="text-sm text-muted-foreground">亚军</span>
        )
      ) : visualStatus === 'live' && isServing ? (
        <div
          id="server-indicator"
          className={cn(
            'flex items-center gap-2 rounded-lg px-2 py-1 text-sm font-medium text-primary transition-[box-shadow,background-color]',
            highlight === 'server' && 'bg-primary/10 ring-2 ring-primary/70',
          )}
          aria-live="polite"
        >
          <span className="live-pulse size-2 rounded-full bg-primary" aria-hidden="true" />
          当前发球
        </div>
      ) : visualStatus === 'live' ? (
        <span className="text-sm text-muted-foreground">接发球</span>
      ) : (
        <span className="text-sm text-muted-foreground">状态待确认</span>
      )}
    </div>
  )
}

function ScheduledMatch({ match, preview }: { match: MatchViewModel; preview: boolean }) {
  return (
    <div className="flex min-h-40 flex-col items-center justify-center gap-2 rounded-xl bg-background/35 p-4 text-center">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Clock3 aria-hidden="true" className="size-4 text-primary" />
        预计开赛
      </div>
      <p className="font-mono text-4xl font-semibold tracking-tighter sm:text-5xl">
        {match.scheduledTime}
      </p>
      <p className="text-sm text-muted-foreground">
        {match.scheduledDate} · {preview ? previewMatchMeta.timezone : match.timezoneLabel}
      </p>
      <Badge variant="secondary">{preview ? '赛前简报已就绪' : match.format}</Badge>
    </div>
  )
}

function scoreRows(match: MatchViewModel, score: MatchScoreDto) {
  return match.players.map((player, index) => ({
    player,
    serving: match.serverPlayerId === player.id,
    sets: score.sets.map((set) =>
      index === 0 ? set.player1_games ?? null : set.player2_games ?? null,
    ),
    points: score.points[index] ?? null,
  }))
}

function LiveScore({
  match,
  highlight,
  preview,
}: {
  match: MatchViewModel
  highlight: MatchHighlight
  preview: boolean
}) {
  const score = match.score
  if (!score) return null
  const rows = scoreRows(match, score)
  const setCount = score.sets.length

  return (
    <div
      id="live-scoreboard"
      className={cn(
        'flex min-h-40 flex-col justify-center gap-4 rounded-xl p-3 transition-[box-shadow,background-color]',
        highlight === 'score' && 'bg-primary/5 ring-2 ring-primary/60',
      )}
      aria-live="polite"
    >
      <div className="flex flex-wrap items-center justify-center gap-2 text-sm font-medium text-primary">
        <Radio aria-hidden="true" className="size-4" />
        {preview
          ? <>第 {previewMatchMeta.currentSet} 盘 · 第 {previewMatchMeta.currentGame} 局</>
          : <>第 {setCount} 盘</>}
        <span className="font-mono text-muted-foreground">
          {preview ? previewMatchMeta.liveElapsed : match.freshnessLabel}
        </span>
      </div>

      <table className="w-full table-fixed text-center" aria-label="实时比赛比分">
        <caption className="sr-only">
          {match.players[0].name} 对阵 {match.players[1].name} 的逐盘比分与当前局分
        </caption>
        <thead>
          <tr className="font-mono text-xs text-muted-foreground sm:text-sm">
            <th scope="col" className="w-20 text-left font-normal">球员</th>
            {score.sets.map((set) => (
              <th key={set.number} scope="col" className={cn('font-normal', set.number === setCount && 'text-primary')}>
                {set.number}
              </th>
            ))}
            <th scope="col" className="font-normal">局分</th>
          </tr>
        </thead>
        <tbody className="font-mono text-2xl font-semibold tabular-nums sm:text-3xl">
          {rows.map((row) => (
            <tr key={row.player.id}>
              <th scope="row" className="py-2 text-left font-sans text-sm font-medium">
                <span className="flex items-center gap-2">
                  {row.serving ? <span className="size-2 rounded-full bg-primary" aria-label="发球方" /> : null}
                  {row.player.shortName}
                </span>
              </th>
              {row.sets.map((games, index) => (
                <td key={`${row.player.id}-${index}`} className={cn('py-2', index === setCount - 1 && 'text-primary')}>
                  {games ?? '-'}
                </td>
              ))}
              <td className="py-2 text-foreground">{row.points ?? ''}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="flex flex-wrap items-center justify-center gap-2 text-sm text-muted-foreground">
        <span>
          {match.serverPlayerId
            ? `${match.players.find((player) => player.id === match.serverPlayerId)?.shortName ?? ''} 发球`
            : match.visualStatus === 'upcoming'
              ? '开赛前未产生发球方'
              : '官方未返回发球方'}
        </span>
        <span aria-hidden="true">·</span>
        <span>当前局 {score.points[0] ?? '–'}–{score.points[1] ?? '–'}</span>
        <span aria-hidden="true">·</span>
        <span>
          {setLabel(setCount - 1)} {rows[0].sets[setCount - 1] ?? '-'}–{rows[1].sets[setCount - 1] ?? '-'}
        </span>
      </div>
    </div>
  )
}

function FinishedScore({
  match,
  highlight,
  preview,
}: {
  match: MatchViewModel
  highlight: MatchHighlight
  preview: boolean
}) {
  const score = match.score
  if (!score) return null
  const rows = scoreRows(match, score)
  const winner = match.players.find((player) => player.id === match.winnerPlayerId)
  const setsSummary = rows[0].sets
    .map((games, index) => `${games ?? '-'}–${rows[1].sets[index] ?? '-'}`)
    .join('、')

  return (
    <div
      id="final-scoreboard"
      className={cn(
        'flex min-h-40 flex-col justify-center gap-4 rounded-xl p-3 transition-[box-shadow,background-color]',
        highlight === 'score' && 'bg-primary/5 ring-2 ring-primary/60',
      )}
      aria-live="polite"
    >
      <div className="flex items-center justify-center gap-2 text-sm font-medium text-primary">
        <Trophy aria-hidden="true" className="size-4" />
        {winner ? `${winner.shortName} 获胜` : '比赛已结束'} · {preview ? previewMatchMeta.finalDuration : match.freshnessLabel}
      </div>
      <table className="w-full table-fixed text-center" aria-label="最终比赛比分">
        <caption className="sr-only">
          {match.players[0].name} 对阵 {match.players[1].name} 的最终逐盘比分
        </caption>
        <thead>
          <tr className="font-mono text-xs text-muted-foreground sm:text-sm">
            <th scope="col" className="w-20 text-left font-normal">球员</th>
            {score.sets.map((set) => (
              <th key={set.number} scope="col" className="font-normal">{set.number}</th>
            ))}
          </tr>
        </thead>
        <tbody className="font-mono text-2xl font-semibold tabular-nums sm:text-3xl">
          {rows.map((row) => (
            <tr key={row.player.id} className={row.player.id === match.winnerPlayerId ? 'text-primary' : undefined}>
              <th scope="row" className="py-2 text-left font-sans text-sm font-medium">
                {row.player.shortName}
              </th>
              {row.sets.map((games, index) => (
                <td key={`${row.player.id}-${index}`} className="py-2">{games ?? '-'}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-center text-sm text-muted-foreground">最终比分 {setsSummary}</p>
    </div>
  )
}

export function MatchHero({ match, highlight, onAsk, onRefresh, preview = false }: MatchHeroProps) {
  const visualStatus = match.visualStatus
  const isLive = visualStatus === 'live'
  const isFinished = visualStatus === 'finished'

  return (
    <Card id="match" data-tone="hero" className="relative">
      <CardHeader className="border-b">
        <CardTitle>
          <h1 className="text-balance text-base font-semibold">
            {isFinished
              ? `${match.players[0].name} 击败 ${match.players[1].name}`
              : `${match.players[0].name} 对阵 ${match.players[1].name}`}
          </h1>
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          {preview
            ? `${previewMatchMeta.tournament} · ${previewMatchMeta.event} · ${previewMatchMeta.surface}`
            : `${match.tournament} · ${match.round} · ${match.surface}`}
        </p>
        <CardAction>
          {isLive ? (
            <Badge variant="destructive" role="status">
              <span className="live-pulse size-1.5 rounded-full bg-current" aria-hidden="true" />
              直播
            </Badge>
          ) : isFinished ? (
            <Badge variant="secondary" role="status">已完赛</Badge>
          ) : visualStatus === 'upcoming' ? (
            <Badge variant="outline" role="status">即将开始</Badge>
          ) : (
            <Badge variant="outline" role="status">状态待确认</Badge>
          )}
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-5 pt-1">
        <div className="grid grid-cols-2 gap-5 lg:grid-cols-[1fr_1.35fr_1fr] lg:items-center">
          <PlayerSummary
            player={match.players[0]}
            previewPlayer={preview ? getPreviewPlayer(match.players[0].id) : null}
            side="left"
            visualStatus={visualStatus}
            isServing={match.serverPlayerId === match.players[0].id}
            isWinner={match.winnerPlayerId === match.players[0].id}
            highlight={highlight}
          />
          <div className="order-3 col-span-2 lg:order-none lg:col-span-1">
            {visualStatus === 'upcoming' || visualStatus === 'unavailable' ? (
              <ScheduledMatch match={match} preview={preview} />
            ) : null}
            {isLive ? <LiveScore match={match} highlight={highlight} preview={preview} /> : null}
            {isFinished ? <FinishedScore match={match} highlight={highlight} preview={preview} /> : null}
          </div>
          <PlayerSummary
            player={match.players[1]}
            previewPlayer={preview ? getPreviewPlayer(match.players[1].id) : null}
            side="right"
            visualStatus={visualStatus}
            isServing={match.serverPlayerId === match.players[1].id}
            isWinner={match.winnerPlayerId === match.players[1].id}
            highlight={highlight}
          />
        </div>
      </CardContent>

      <CardFooter className="flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
        <div className="flex w-full gap-2 sm:w-auto">
          <Button className="w-full sm:w-auto" onClick={onAsk}>
            <Sparkles data-icon="inline-start" aria-hidden="true" />
            询问本场比赛
          </Button>
          {onRefresh ? (
            <Button variant="outline" className="w-full sm:w-auto" onClick={onRefresh} aria-label="刷新比赛数据">
              <RefreshCw aria-hidden="true" />
            </Button>
          ) : null}
        </div>
        <p className="text-sm leading-relaxed text-muted-foreground">
          {preview
            ? visualStatus === 'upcoming'
              ? '赛程与背景资料已同步'
              : visualStatus === 'live'
                ? '实时数据延迟约 2.4 秒'
                : '最终比分与赛后摘要已核验'
            : match.freshnessLabel}
        </p>
      </CardFooter>
    </Card>
  )
}
