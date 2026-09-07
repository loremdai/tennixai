import {
  Clock3,
  Radio,
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
import { cn } from '@/lib/utils'

import {
  finishedScore,
  getPlayer,
  liveScore,
  matchMeta,
  type MatchHighlight,
  type MatchStatus,
  type Player,
  players,
} from './match-data'

type MatchHeroProps = {
  status: MatchStatus
  highlight: MatchHighlight
  onAsk: () => void
}

function PlayerSummary({
  player,
  side,
  status,
  isServing,
  isWinner,
  highlight,
}: {
  player: Player
  side: 'left' | 'right'
  status: MatchStatus
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
        <img
          src={player.flagUrl}
          alt={`${player.country}国旗`}
          width={20}
          height={14}
          loading="eager"
          fetchPriority="high"
          className="h-3.5 w-5 rounded-sm object-cover ring-1 ring-border"
        />
        <span className="font-mono text-xs text-muted-foreground">{player.countryCode}</span>
        <Badge variant="outline">{player.seed} 号种子</Badge>
      </div>

      <div className="min-w-0">
        <p className="text-pretty text-lg font-semibold leading-tight tracking-tight sm:text-2xl lg:text-3xl">
          {player.name}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">世界排名 #{player.rank}</p>
      </div>

      {status === 'upcoming' ? (
        <span className="text-sm text-muted-foreground">赛前档案</span>
      ) : status === 'finished' ? (
        isWinner ? (
          <Badge variant="secondary">
            <Trophy data-icon="inline-start" aria-hidden="true" />
            胜者
          </Badge>
        ) : (
          <span className="text-sm text-muted-foreground">亚军</span>
        )
      ) : isServing ? (
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
      ) : (
        <span className="text-sm text-muted-foreground">接发球</span>
      )}
    </div>
  )
}

function ScheduledMatch() {
  return (
    <div className="flex min-h-40 flex-col items-center justify-center gap-2 rounded-xl bg-background/35 p-4 text-center">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Clock3 aria-hidden="true" className="size-4 text-primary" />
        预计开赛
      </div>
      <p className="font-mono text-4xl font-semibold tracking-tighter sm:text-5xl">
        {matchMeta.scheduledTime}
      </p>
      <p className="text-sm text-muted-foreground">
        {matchMeta.scheduledDate} · {matchMeta.timezone}
      </p>
      <Badge variant="secondary">赛前简报已就绪</Badge>
    </div>
  )
}

function LiveScore({ highlight }: { highlight: MatchHighlight }) {
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
        第 {matchMeta.currentSet} 盘 · 第 {matchMeta.currentGame} 局
        <span className="font-mono text-muted-foreground">{matchMeta.liveElapsed}</span>
      </div>

      <table className="w-full table-fixed text-center" aria-label="实时比赛比分">
        <caption className="sr-only">Jannik Sinner 对阵 Carlos Alcaraz 的逐盘比分与当前局分</caption>
        <thead>
          <tr className="font-mono text-xs text-muted-foreground sm:text-sm">
            <th scope="col" className="w-20 text-left font-normal">球员</th>
            <th scope="col" className="font-normal">1</th>
            <th scope="col" className="font-normal">2</th>
            <th scope="col" className="font-normal text-primary">3</th>
            <th scope="col" className="font-normal">局分</th>
          </tr>
        </thead>
        <tbody className="font-mono text-2xl font-semibold tabular-nums sm:text-3xl">
          {liveScore.rows.map((row) => {
            const player = getPlayer(row.playerId)
            return (
              <tr key={row.playerId}>
                <th scope="row" className="py-2 text-left font-sans text-sm font-medium">
                  <span className="flex items-center gap-2">
                    {row.serving ? <span className="size-2 rounded-full bg-primary" aria-label="发球方" /> : null}
                    {player.shortName}
                  </span>
                </th>
                {row.sets.map((score, index) => (
                  <td key={`${row.playerId}-${index}`} className={cn('py-2', index === 2 && 'text-primary')}>
                    {score}
                  </td>
                ))}
                <td className="py-2 text-foreground">{row.points}</td>
              </tr>
            )
          })}
        </tbody>
      </table>

      <div className="flex flex-wrap items-center justify-center gap-2 text-sm text-muted-foreground">
        <span>Sinner 发球</span>
        <span aria-hidden="true">·</span>
        <span>当前局 30–15</span>
        <span aria-hidden="true">·</span>
        <span>第三盘 4–5</span>
      </div>
    </div>
  )
}

function FinishedScore({ highlight }: { highlight: MatchHighlight }) {
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
        Sinner 获胜 · {matchMeta.finalDuration}
      </div>
      <table className="w-full table-fixed text-center" aria-label="最终比赛比分">
        <caption className="sr-only">Jannik Sinner 以 6–4、4–6、6–3 击败 Carlos Alcaraz</caption>
        <thead>
          <tr className="font-mono text-xs text-muted-foreground sm:text-sm">
            <th scope="col" className="w-20 text-left font-normal">球员</th>
            <th scope="col" className="font-normal">1</th>
            <th scope="col" className="font-normal">2</th>
            <th scope="col" className="font-normal">3</th>
          </tr>
        </thead>
        <tbody className="font-mono text-2xl font-semibold tabular-nums sm:text-3xl">
          {finishedScore.rows.map((row) => {
            const player = getPlayer(row.playerId)
            return (
              <tr key={row.playerId} className={row.winner ? 'text-primary' : undefined}>
                <th scope="row" className="py-2 text-left font-sans text-sm font-medium">
                  {player.shortName}
                </th>
                {row.sets.map((score, index) => (
                  <td key={`${row.playerId}-${index}`} className="py-2">{score}</td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
      <p className="text-center text-sm text-muted-foreground">最终比分 6–4、4–6、6–3</p>
    </div>
  )
}

export function MatchHero({ status, highlight, onAsk }: MatchHeroProps) {
  const isLive = status === 'live'
  const isFinished = status === 'finished'

  return (
    <Card id="match" data-tone="hero" className="relative">
      <CardHeader className="border-b">
        <CardTitle>
          <h1 className="text-balance text-base font-semibold">
            {isFinished
              ? `${players[0].name} 击败 ${players[1].name}`
              : `${players[0].name} 对阵 ${players[1].name}`}
          </h1>
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          {matchMeta.tournament} · {matchMeta.event} · {matchMeta.surface}
        </p>
        <CardAction>
          {isLive ? (
            <Badge variant="destructive" role="status">
              <span className="live-pulse size-1.5 rounded-full bg-current" aria-hidden="true" />
              直播
            </Badge>
          ) : isFinished ? (
            <Badge variant="secondary" role="status">已完赛</Badge>
          ) : (
            <Badge variant="outline" role="status">即将开始</Badge>
          )}
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-5 pt-1">
        <div className="grid grid-cols-2 gap-5 lg:grid-cols-[1fr_1.35fr_1fr] lg:items-center">
          <PlayerSummary
            player={players[0]}
            side="left"
            status={status}
            isServing={isLive}
            isWinner={isFinished}
            highlight={highlight}
          />
          <div className="order-3 col-span-2 lg:order-none lg:col-span-1">
            {status === 'upcoming' ? <ScheduledMatch /> : null}
            {status === 'live' ? <LiveScore highlight={highlight} /> : null}
            {status === 'finished' ? <FinishedScore highlight={highlight} /> : null}
          </div>
          <PlayerSummary
            player={players[1]}
            side="right"
            status={status}
            isServing={false}
            isWinner={false}
            highlight={highlight}
          />
        </div>
      </CardContent>

      <CardFooter className="flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
        <Button className="w-full sm:w-auto" onClick={onAsk}>
          <Sparkles data-icon="inline-start" aria-hidden="true" />
          询问本场比赛
        </Button>
        <p className="text-sm leading-relaxed text-muted-foreground">
          {status === 'upcoming'
            ? '赛程与背景资料已同步'
            : status === 'live'
              ? '实时数据延迟约 2.4 秒'
              : '最终比分与赛后摘要已核验'}
        </p>
      </CardFooter>
    </Card>
  )
}
