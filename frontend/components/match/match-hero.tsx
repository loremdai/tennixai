import {
  Clock3,
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
  CardContent,
  CardFooter,
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
    <div className="flex min-w-0 items-center gap-2 sm:gap-3 lg:gap-4">
      <PlayerAvatar
        name={player.name}
        imageUrl={player.avatarUrl}
        className="size-10 shrink-0 border border-white/20 bg-background sm:size-14 md:size-16"
      />
      <div className="min-w-0 flex-1">
        <PlayerName
          name={player.name}
          localizedName={player.nameZh}
          className="min-w-0 max-w-full !whitespace-normal"
          primaryClassName="!overflow-visible !text-clip !whitespace-normal break-words [overflow-wrap:anywhere] text-sm font-semibold leading-tight tracking-tight sm:text-lg lg:text-xl"
          secondaryClassName="mt-0.5 !overflow-visible !text-clip !whitespace-normal break-words [overflow-wrap:anywhere] text-xs leading-snug sm:text-sm"
        />
        <div className="mt-1 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted-foreground sm:mt-2 sm:text-xs lg:text-sm">
          {previewPlayer ? (
            <span className="inline-flex items-center" aria-label={`${previewPlayer.country}（${previewPlayer.countryCode}）`}>
              <img
                src={previewPlayer.flagUrl}
                alt={`${previewPlayer.country}国旗`}
                width={20}
                height={14}
                loading="eager"
                fetchPriority="high"
                className="h-3.5 w-5 rounded-sm object-cover ring-1 ring-border"
              />
            </span>
          ) : (
            <PlayerCountry player={player} />
          )}
          {ranking !== null ? <span>世界排名 #{ranking}</span> : null}
          {isServing ? (
            <span
              id="server-indicator"
              className={cn(
                'inline-flex items-center gap-1 font-medium text-primary transition-[box-shadow,background-color]',
                highlight === 'server' && 'bg-primary/10 ring-2 ring-primary/70',
              )}
              aria-live="polite"
            >
              <span className="live-pulse size-1.5 rounded-full bg-primary" aria-hidden="true" />
              发球
            </span>
          ) : null}
          {isWinner ? (
            <Badge variant="secondary" className="h-5 px-1.5 text-[10px] text-primary">
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
    <div className="flex min-h-28 flex-col items-center justify-center gap-1 border-t border-white/10 py-4 text-center md:border-t-0 md:border-l md:py-2">
      <div className="flex items-center gap-2 text-sm text-muted-foreground sm:text-base">
        <Clock3 aria-hidden="true" className="size-4 text-primary" />
        预计开赛
      </div>
      <p className="font-mono text-3xl font-semibold tracking-tight sm:text-4xl">
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

function TennisBall() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" className="size-4 text-primary sm:size-5">
      <circle cx="12" cy="12" r="10" fill="currentColor" />
      <path d="M5 5c5 4 5 10 0 14M19 5c-5 4-5 10 0 14" stroke="var(--background)" strokeWidth="1.5" />
    </svg>
  )
}

function currentGameLabel(score: MatchScoreDto, currentSetNumber: number | null, preview: boolean) {
  if (preview) return `第 ${previewMatchMeta.currentSet} 盘 · 第 ${previewMatchMeta.currentGame} 局`
  if (currentSetNumber === null) return '当前盘比分暂未提供'
  if (score.is_tiebreak) return `第 ${currentSetNumber} 盘 · 抢七`
  const currentSet = score.sets.find((set) => set.number === currentSetNumber)
  if (
    currentSet?.player1_games == null ||
    currentSet.player2_games == null ||
    score.points.every((point) => point == null)
  ) {
    return `第 ${currentSetNumber} 盘`
  }
  return `第 ${currentSetNumber} 盘 · 第 ${currentSet.player1_games + currentSet.player2_games + 1} 局`
}

function playerColumnWidth(setCount: number, live: boolean) {
  if (setCount >= 5) return live ? 'w-[45%] sm:w-[52%]' : 'w-[45%] sm:w-[54%]'
  if (setCount === 4) return live ? 'w-[49%] sm:w-[55%]' : 'w-[49%] sm:w-[57%]'
  return live ? 'w-[52%] sm:w-[58%]' : 'w-[52%] sm:w-[60%]'
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
        'transition-[box-shadow,background-color]',
        highlight === 'score' && 'bg-primary/5 ring-2 ring-primary/60',
      )}
      aria-live="polite"
    >
      <div className="flex min-h-7 flex-wrap items-center justify-end gap-x-3 gap-y-1 text-right text-xs text-muted-foreground sm:text-sm">
        <span>{currentGameLabel(score, currentSetNumber, preview)}</span>
        {!server ? <span className="text-xs">发球方暂未提供</span> : null}
      </div>

      <table className="w-full table-fixed border-collapse" aria-label="实时比赛比分">
        <caption className="sr-only">实时比赛比分，含逐盘比分与当前局分</caption>
        <colgroup>
          <col className={playerColumnWidth(score.sets.length, true)} />
          {score.sets.map((set) => <col key={set.number} />)}
          <col className="w-[15%] sm:w-[13%]" />
        </colgroup>
        <thead>
          <tr className="text-[10px] text-muted-foreground sm:text-xs lg:text-sm">
            <th scope="col" className="pb-1 text-left font-normal"><span className="sr-only">球员</span></th>
            {score.sets.map((set) => (
              <th
                key={set.number}
                scope="col"
                className={cn('px-0.5 pb-1 text-center font-normal', set.number === currentSetNumber && 'bg-primary/5 text-primary')}
              >
                盘 {set.number}
              </th>
            ))}
            <th scope="col" className="border-l border-white/15 pb-1"><span className="sr-only">当前局</span></th>
          </tr>
        </thead>
        <tbody className="tabular-nums">
          {rows.map((row, rowIndex) => (
            <tr key={row.player.id} className="border-t border-white/10 first:border-t-0">
              <th scope="row" className="py-2 pr-1 text-left font-sans font-normal sm:py-3">
                <ScorePlayerIdentity
                  player={row.player}
                  previewPlayer={preview ? getPreviewPlayer(row.player.id) : null}
                  isServing={false}
                  isWinner={false}
                />
              </th>
              {row.sets.map((games, index) => {
                const current = score.sets[index]?.number === currentSetNumber
                const otherGames = rows[1 - rowIndex]?.sets[index]
                return (
                  <td
                    key={`${row.player.id}-${index}`}
                    className={cn(
                      'px-0.5 py-2 text-center font-mono text-xl font-semibold sm:py-3 sm:text-2xl lg:text-3xl',
                      current ? 'bg-primary/5 text-primary' : games != null && otherGames != null && games < otherGames ? 'text-muted-foreground' : 'text-foreground',
                    )}
                  >
                    {games ?? '–'}
                    {row.tiebreakPoints[index] != null ? (
                      <span className="block text-[10px] font-normal leading-tight text-muted-foreground sm:text-xs">
                        （{row.tiebreakPoints[index]}）
                      </span>
                    ) : null}
                  </td>
                )
              })}
              <td className="border-l border-white/15 px-0.5 py-2 text-center font-mono text-xl font-semibold text-foreground sm:py-3 sm:text-2xl lg:text-3xl">
                <span className={cn(
                  'inline-flex items-center justify-center',
                  score.sets.length >= 4 ? 'flex-col gap-0 sm:flex-row sm:gap-2' : 'gap-1 sm:gap-2',
                )}>
                  {row.points ?? '–'}
                  {row.serving ? (
                    <span
                      id="server-indicator"
                      aria-label={`${row.player.name} 发球`}
                      className={cn('inline-flex text-primary', highlight === 'server' && 'rounded-full bg-primary/10 ring-2 ring-primary/70')}
                    >
                      <TennisBall />
                      <span className="sr-only">发球</span>
                    </span>
                  ) : null}
                </span>
              </td>
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
        'transition-[box-shadow,background-color]',
        highlight === 'score' && 'bg-primary/5 ring-2 ring-primary/60',
      )}
      aria-live="polite"
    >
      <table className="w-full table-fixed border-collapse" aria-label="最终比赛比分">
        <caption className="sr-only">最终比分，含逐盘比分</caption>
        <colgroup>
          <col className={playerColumnWidth(score.sets.length, false)} />
          {score.sets.map((set) => <col key={set.number} />)}
        </colgroup>
        <thead>
          <tr className="text-[10px] text-muted-foreground sm:text-xs lg:text-sm">
            <th scope="col" className="pb-1 text-left font-normal"><span className="sr-only">球员</span></th>
            {score.sets.map((set) => (
              <th key={set.number} scope="col" className="px-0.5 pb-1 text-center font-normal">盘 {set.number}</th>
            ))}
          </tr>
        </thead>
        <tbody className="tabular-nums">
          {rows.map((row, rowIndex) => {
            const isWinner = row.player.id === match.winnerPlayerId
            return (
              <tr key={row.player.id} className="border-t border-white/10 first:border-t-0">
                <th scope="row" className="py-2 pr-1 text-left font-sans font-normal sm:py-3">
                  <ScorePlayerIdentity
                    player={row.player}
                    previewPlayer={preview ? getPreviewPlayer(row.player.id) : null}
                    isServing={false}
                    isWinner={isWinner}
                  />
                </th>
                {row.sets.map((games, index) => {
                  const otherGames = rows[1 - rowIndex]?.sets[index]
                  return (
                    <td
                      key={`${row.player.id}-${index}`}
                      className={cn(
                        'px-0.5 py-2 text-center font-mono text-xl font-semibold sm:py-3 sm:text-2xl lg:text-3xl',
                        games != null && otherGames != null && games < otherGames ? 'text-muted-foreground' : 'text-foreground',
                      )}
                    >
                      {games ?? '–'}
                      {row.tiebreakPoints[index] != null ? (
                        <span className="block text-[10px] font-normal leading-tight text-muted-foreground sm:text-xs">
                          （{row.tiebreakPoints[index]}）
                        </span>
                      ) : null}
                    </td>
                  )
                })}
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
    <div className="divide-y divide-white/10">
      {match.players.map((player) => (
        <div key={player.id} className="py-2 sm:py-3 lg:py-4">
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
  const updateLabel = preview
    ? '北京 20:42 更新'
    : match.freshnessLabel.startsWith('更新于 ')
      ? `北京 ${match.freshnessLabel.slice(4)} 更新`
      : match.freshnessLabel

  return (
    <Card id="match" data-tone="hero" className="relative !gap-0 !bg-[#0b1114] !py-0">
      <div className="flex items-start justify-between gap-2 border-b border-white/15 px-5 py-3 sm:items-center sm:gap-4 sm:px-6 sm:py-4 lg:px-8 lg:py-5">
        <div className="min-w-0 border-l-4 border-primary pl-3 sm:pl-4">
          <h1 className="text-balance text-lg font-medium leading-tight tracking-tight sm:text-xl">{tournament}</h1>
          <p className="mt-1 text-xs text-muted-foreground sm:text-sm">{matchDetails}</p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1 text-[10px] text-muted-foreground sm:flex-row sm:items-center sm:gap-3 sm:text-xs lg:text-sm">
          {isLive ? (
            <Badge variant="outline" role="status" aria-label="直播中" className="h-7 gap-1.5 border-primary/10 bg-primary/5 px-2 text-xs font-semibold tracking-wide text-primary sm:h-8 sm:px-3 sm:text-sm">
              <span className="live-pulse size-2 rounded-full bg-primary" aria-hidden="true" />
              LIVE
            </Badge>
          ) : isFinished ? (
            <Badge variant="secondary" role="status" className="h-7 px-2 sm:h-8 sm:px-3">已完赛</Badge>
          ) : visualStatus === 'upcoming' ? (
            <Badge variant="outline" role="status" className="h-7 px-2 sm:h-8 sm:px-3">即将开始</Badge>
          ) : (
            <Badge variant="outline" role="status" className="h-7 px-2 sm:h-8 sm:px-3">比赛信息待更新</Badge>
          )}
          <span className="hidden h-5 w-px bg-white/20 sm:block" aria-hidden="true" />
          <span>{updateLabel}</span>
        </div>
      </div>

      <CardContent className="flex flex-col gap-2 !px-5 !pt-2 !pb-3 sm:!px-6 sm:!pt-3 sm:!pb-4 lg:!px-8">
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
        {visualStatus === 'upcoming' ? (
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(12rem,0.48fr)] md:items-center">
            <PlayerList match={match} preview={preview} />
            <ScheduledMatch match={match} preview={preview} />
          </div>
        ) : null}
        {visualStatus === 'unavailable' ? (
          <>
            <PlayerList match={match} preview={preview} />
            <p className="text-sm text-muted-foreground">目前无法获取这场比赛的比分，请稍后再看。</p>
          </>
        ) : null}
      </CardContent>

      <CardFooter className="flex flex-col items-start justify-end gap-3 !border-white/10 !bg-transparent !px-5 !py-3 sm:flex-row sm:items-center sm:!px-6 lg:!px-8">
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
