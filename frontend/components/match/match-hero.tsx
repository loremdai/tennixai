import {
  Clock3,
  Radio,
  RefreshCw,
  Sparkles,
  Trophy,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { PlayerCountry } from '@/components/player-country'
import { PlayerAvatar } from '@/components/player-avatar'
import { PlayerName } from '@/components/player-name'
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

function ScorePlayerIdentity({
  player,
  previewPlayer,
  isServing,
  isWinner,
  highlight,
}: {
  player: MatchViewModel['players'][number]
  previewPlayer: PreviewPlayer | null
  isServing: boolean
  isWinner: boolean
  highlight?: MatchHighlight
}) {
  const ranking = previewPlayer?.rank ?? player.ranking

  return (
    <div className="flex min-w-0 items-center gap-2 sm:gap-3">
      <PlayerAvatar name={player.name} imageUrl={player.avatarUrl} className="size-9 shrink-0 sm:size-11" />
      <div className="min-w-0 flex-1">
        <PlayerName
          name={player.name}
          localizedName={player.nameZh}
          className="min-w-0 flex-1 !whitespace-normal"
          primaryClassName="text-sm font-semibold leading-tight !overflow-visible !text-clip !whitespace-normal break-words [overflow-wrap:anywhere] sm:text-base"
          secondaryClassName="!overflow-visible !text-clip !whitespace-normal text-[11px] sm:text-xs"
        />
        <div className="mt-1 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-[11px] leading-none text-muted-foreground sm:text-xs">
          {previewPlayer ? (
            <span className="inline-flex items-center gap-1.5" aria-label={`${previewPlayer.country}（${previewPlayer.countryCode}）`}>
              <img
                src={previewPlayer.flagUrl}
                alt={`${previewPlayer.country}国旗`}
                width={18}
                height={13}
                loading="eager"
                fetchPriority="high"
                className="h-[13px] w-[18px] rounded-sm object-cover ring-1 ring-border"
              />
              <span className="font-mono">{previewPlayer.countryCode}</span>
            </span>
          ) : (
            <PlayerCountry player={player} showCode />
          )}
          {ranking !== null ? <span className="font-mono">#{ranking}</span> : null}
          {isServing ? (
            <span
              id="server-indicator"
              className={cn(
                'inline-flex items-center gap-1 rounded px-1 font-medium text-primary transition-[box-shadow,background-color]',
                highlight === 'server' && 'bg-primary/10 ring-2 ring-primary/70',
              )}
              aria-live="polite"
            >
              <span className="live-pulse size-1.5 rounded-full bg-primary" aria-hidden="true" />
              发球
            </span>
          ) : null}
          {isWinner ? (
            <Badge variant="secondary" className="h-5 px-1.5 text-[10px]">
              <Trophy data-icon="inline-start" aria-hidden="true" />
              胜者
            </Badge>
          ) : null}
        </div>
      </div>
    </div>
  )
}

function ScheduledMatch({ match, preview }: { match: MatchViewModel; preview: boolean }) {
  return (
    <div className="flex min-h-28 flex-col items-center justify-center gap-2 rounded-xl bg-background/35 p-4 text-center">
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
      {!preview && match.isStale ? <p className="text-xs text-muted-foreground">{match.freshnessLabel}</p> : null}
    </div>
  )
}

function knownServerPlayerId(match: MatchViewModel): string | null {
  return match.players.some((player) => player.id === match.serverPlayerId)
    ? match.serverPlayerId
    : null
}

function scoreRows(match: MatchViewModel, score: MatchScoreDto) {
  const serverPlayerId = knownServerPlayerId(match)
  return match.players.map((player, index) => ({
    player,
    serving: serverPlayerId === player.id,
    sets: score.sets.map((set) =>
      index === 0 ? set.player1_games ?? null : set.player2_games ?? null,
    ),
    tiebreakPoints: score.sets.map((set) => {
      if (
        set.player1_tiebreak_points == null ||
        set.player2_tiebreak_points == null
      ) {
        return null
      }
      return index === 0 ? set.player1_tiebreak_points : set.player2_tiebreak_points
    }),
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
  const currentSetNumber = preview ? previewMatchMeta.currentSet : match.currentSetNumber
  const server = match.players.find((player) => player.id === knownServerPlayerId(match))

  return (
    <div
      id="live-scoreboard"
      className={cn(
        'flex flex-col justify-center gap-3 rounded-xl bg-background/35 p-3 transition-[box-shadow,background-color] sm:p-4',
        highlight === 'score' && 'bg-primary/5 ring-2 ring-primary/60',
      )}
      aria-live="polite"
    >
      <div className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-sm font-medium text-primary">
        <Radio aria-hidden="true" className="size-4" />
        {preview
          ? <>第 {previewMatchMeta.currentSet} 盘 · 第 {previewMatchMeta.currentGame} 局</>
          : currentSetNumber !== null
            ? <>第 {currentSetNumber} 盘</>
            : <>当前盘比分暂未提供</>}
        <span className="font-mono text-muted-foreground">
          {preview ? previewMatchMeta.liveElapsed : match.freshnessLabel}
        </span>
        {!server ? <span className="text-xs font-normal text-muted-foreground">发球方暂未提供</span> : null}
      </div>

      <table className="w-full table-fixed text-center" aria-label="实时比赛比分">
        <caption className="sr-only">
          实时比赛比分，含逐盘比分与当前局分
        </caption>
        <thead>
          <tr className="font-mono text-[11px] text-muted-foreground sm:text-xs">
            <th scope="col" className="w-[42%] text-left font-normal">球员</th>
            {score.sets.map((set) => (
              <th
                key={set.number}
                scope="col"
                className={cn('px-0.5 font-normal', set.number === currentSetNumber && 'text-primary')}
              >
                {set.number}
              </th>
            ))}
            <th scope="col" className="w-[13%] px-0.5 font-normal">当前局</th>
          </tr>
        </thead>
        <tbody className="font-mono text-xl font-semibold tabular-nums sm:text-2xl">
          {rows.map((row) => (
            <tr key={row.player.id} className="border-t border-border/60">
              <th scope="row" className="py-2 pr-1 text-left font-sans font-medium">
                <ScorePlayerIdentity
                  player={row.player}
                  previewPlayer={preview ? getPreviewPlayer(row.player.id) : null}
                  isServing={row.serving}
                  isWinner={false}
                  highlight={highlight}
                />
              </th>
              {row.sets.map((games, index) => (
                <td
                  key={`${row.player.id}-${index}`}
                  className={cn('px-0.5 py-2', score.sets[index]?.number === currentSetNumber && 'text-primary')}
                >
                  {games ?? '-'}
                  {row.tiebreakPoints[index] != null ? (
                    <span className="block text-xs font-medium leading-tight text-muted-foreground sm:inline sm:text-[0.65em]">
                      （{row.tiebreakPoints[index]}）
                    </span>
                  ) : null}
                </td>
              ))}
              <td className="px-0.5 py-2 text-foreground">{row.points ?? '–'}</td>
            </tr>
          ))}
        </tbody>
      </table>
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
  return (
    <div
      id="final-scoreboard"
      className={cn(
        'flex flex-col justify-center gap-3 rounded-xl bg-background/35 p-3 transition-[box-shadow,background-color] sm:p-4',
        highlight === 'score' && 'bg-primary/5 ring-2 ring-primary/60',
      )}
      aria-live="polite"
    >
      <div className="flex items-center justify-center gap-2 text-sm font-medium text-primary">
        <Trophy aria-hidden="true" className="size-4" />
        最终比分
        <span className="font-mono text-xs font-normal text-muted-foreground">
          {preview ? previewMatchMeta.finalDuration : match.freshnessLabel}
        </span>
      </div>
      <table className="w-full table-fixed text-center" aria-label="最终比赛比分">
        <caption className="sr-only">
          最终比分，含逐盘比分
        </caption>
        <thead>
          <tr className="font-mono text-[11px] text-muted-foreground sm:text-xs">
            <th scope="col" className="w-[42%] text-left font-normal">球员</th>
            {score.sets.map((set) => (
              <th key={set.number} scope="col" className="px-0.5 font-normal">{set.number}</th>
            ))}
          </tr>
        </thead>
        <tbody className="font-mono text-xl font-semibold tabular-nums sm:text-2xl">
          {rows.map((row) => {
            const isWinner = row.player.id === match.winnerPlayerId
            return (
              <tr key={row.player.id} className={cn('border-t border-border/60', isWinner && 'text-primary')}>
                <th scope="row" className="py-2 pr-1 text-left font-sans font-medium">
                  <ScorePlayerIdentity
                    player={row.player}
                    previewPlayer={preview ? getPreviewPlayer(row.player.id) : null}
                    isServing={false}
                    isWinner={isWinner}
                  />
                </th>
                {row.sets.map((games, index) => (
                  <td key={`${row.player.id}-${index}`} className="px-0.5 py-2">
                    {games ?? '-'}
                    {row.tiebreakPoints[index] != null ? (
                      <span className="block text-xs font-medium leading-tight text-muted-foreground sm:inline sm:text-[0.65em]">
                        （{row.tiebreakPoints[index]}）
                      </span>
                    ) : null}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function PlayerList({
  match,
  preview,
  serverPlayerId = null,
  winnerPlayerId = null,
  highlight,
}: {
  match: MatchViewModel
  preview: boolean
  serverPlayerId?: string | null
  winnerPlayerId?: string | null
  highlight?: MatchHighlight
}) {
  return (
    <div className="divide-y divide-border/60 rounded-xl bg-background/35 px-3">
      {match.players.map((player) => (
        <div key={player.id} className="py-3">
          <ScorePlayerIdentity
            player={player}
            previewPlayer={preview ? getPreviewPlayer(player.id) : null}
            isServing={player.id === serverPlayerId}
            isWinner={player.id === winnerPlayerId}
            highlight={highlight}
          />
        </div>
      ))}
    </div>
  )
}

export function MatchHero({ match, highlight, onAsk, onRefresh, preview = false }: MatchHeroProps) {
  const visualStatus = match.visualStatus
  const isLive = visualStatus === 'live'
  const isFinished = visualStatus === 'finished'
  const serverPlayerId = knownServerPlayerId(match)
  const tournament = preview ? previewMatchMeta.tournament : match.tournament
  const matchDetails = preview
    ? `${previewMatchMeta.event} · ${previewMatchMeta.surface}`
    : `${match.round} · ${match.surface}`

  return (
    <Card id="match" data-tone="hero" className="relative">
      <CardHeader className="border-b">
        <CardTitle>
          <h1 className="text-balance text-base font-semibold">{tournament}</h1>
        </CardTitle>
        <p className="text-sm text-muted-foreground">{matchDetails}</p>
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
            <Badge variant="outline" role="status">比赛信息待更新</Badge>
          )}
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-3 pt-1">
        {isLive ? (
          <>
            {match.score ? (
              <LiveScore match={match} highlight={highlight} preview={preview} />
            ) : (
              <PlayerList
                match={match}
                preview={preview}
                serverPlayerId={serverPlayerId}
                highlight={highlight}
              />
            )}
            {!match.score ? (
              <p className="text-center text-sm text-muted-foreground">实时比分暂未提供</p>
            ) : null}
            {!match.score && !serverPlayerId ? (
              <p className="text-center text-xs text-muted-foreground">发球方暂未提供</p>
            ) : null}
          </>
        ) : null}
        {isFinished ? (
          <>
            {match.score ? (
              <FinishedScore match={match} highlight={highlight} preview={preview} />
            ) : (
              <PlayerList match={match} preview={preview} winnerPlayerId={match.winnerPlayerId} />
            )}
            {!match.score ? (
              <p className="text-center text-sm text-muted-foreground">最终比分暂未提供</p>
            ) : null}
          </>
        ) : null}
        {visualStatus === 'upcoming' || visualStatus === 'unavailable' ? (
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(12rem,0.7fr)] md:items-center">
            <PlayerList match={match} preview={preview} />
            <ScheduledMatch match={match} preview={preview} />
          </div>
        ) : null}
      </CardContent>

      <CardFooter className="flex flex-col items-start justify-end gap-3 sm:flex-row sm:items-center">
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
      </CardFooter>
    </Card>
  )
}
