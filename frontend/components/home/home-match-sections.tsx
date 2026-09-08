'use client'

import { useRef } from 'react'
import Link from 'next/link'
import {
  ArrowRight,
  Clock3,
  RefreshCw,
  Sparkles,
  Star,
} from 'lucide-react'

import { SectionHeading } from '@/components/home/section-heading'
import type { ProductPhase } from '@/components/match/match-data'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import {
  Card,
  CardAction,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import type { HomeMatchViewModel, MatchViewModel } from '@/lib/view-models'
import { cn } from '@/lib/utils'

export type SlateState = 'loading' | 'success' | 'error'

function SlateSectionError({
  title,
  code,
  onRetry,
}: {
  title: string
  code: string | null | undefined
  onRetry: () => void
}) {
  return (
    <div role="alert" className="flex flex-col items-start gap-3 rounded-xl border border-dashed bg-muted/15 p-5">
      <p className="text-sm font-medium">{title}加载失败（{code ?? 'internal_error'}）</p>
      <p className="text-sm text-muted-foreground">该部分暂时不可用，其他比赛信息仍可继续查看。</p>
      <Button variant="outline" onClick={onRetry} aria-label={`重试加载${title}`}>
        <RefreshCw data-icon="inline-start" aria-hidden="true" />
        重试加载
      </Button>
    </div>
  )
}

function FeaturedPlayer({
  player,
  serving,
  align,
  isLive,
}: {
  player: MatchViewModel['players'][number]
  serving: boolean
  align: 'left' | 'right'
  isLive: boolean
}) {
  return (
    <div className={cn('flex items-center gap-3', align === 'right' && 'flex-row-reverse text-right')}>
      <Avatar className="size-12">
        <AvatarFallback>{player.initials}</AvatarFallback>
      </Avatar>
      <div className="min-w-0">
        <div className={cn('flex items-center gap-2', align === 'right' && 'justify-end')}>
          <Badge variant="outline">{player.countryCode}</Badge>
          {player.ranking !== null ? <Badge variant="outline">#{player.ranking}</Badge> : null}
        </div>
        <h3 className="mt-2 text-balance text-base font-semibold leading-tight tracking-tight">{player.name}</h3>
        {isLive ? (
          serving ? (
            <p className={cn('mt-3 flex items-center gap-2 text-xs font-medium text-primary', align === 'right' && 'justify-end')}>
              <span className="live-pulse size-1.5 rounded-full bg-primary" aria-hidden="true" />
              当前发球
            </p>
          ) : (
            <p className="mt-3 text-xs text-muted-foreground">接发球</p>
          )
        ) : (
          <p className="mt-3 text-xs text-muted-foreground">赛前档案</p>
        )}
      </div>
    </div>
  )
}

function FeaturedScore({ match }: { match: MatchViewModel }) {
  const score = match.score
  const setCount = score?.sets.length ?? 0

  return (
    <div className="flex flex-col gap-3 rounded-xl bg-background/45 p-4">
      <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
        <span>{setCount > 0 ? `第 ${setCount} 盘` : '比分暂未提供'}</span>
        <span className="font-mono">{match.freshnessLabel}</span>
      </div>
      {score ? (
        <div
          className="grid items-center gap-3 text-center"
          style={{ gridTemplateColumns: `minmax(0,1fr) repeat(${Math.max(setCount, 1)},2rem) 2.5rem` }}
        >
          <span className="text-left text-xs text-muted-foreground">球员</span>
          {score.sets.map((set) => (
            <span key={set.number} className="font-mono text-xs text-muted-foreground">{set.number}</span>
          ))}
          <span className="font-mono text-xs text-muted-foreground">局分</span>
          {match.players.map((player, index) => {
            const games = score.sets.map((set) =>
              String(index === 0 ? set.player1_games ?? '-' : set.player2_games ?? '-'),
            )
            const serving = match.serverPlayerId === player.id
            return (
              <div key={player.id} className="contents">
                <span className="flex min-w-0 items-center gap-2 text-left text-sm font-medium">
                  {serving ? <span className="size-1.5 shrink-0 rounded-full bg-primary" aria-label="发球方" /> : null}
                  <span className="truncate">{player.shortName}</span>
                </span>
                {games.map((game, setIndex) => (
                  <span key={`${player.id}-${setIndex}`} className="font-mono text-xl font-semibold tabular-nums">{game}</span>
                ))}
                <span className="min-w-7 text-right font-mono text-lg font-semibold text-primary tabular-nums">
                  {score.points[index] ?? ''}
                </span>
              </div>
            )
          })}
        </div>
      ) : null}
      <p className="border-t pt-3 text-center text-xs text-muted-foreground">
        {match.serverPlayerId
          ? `${match.players.find((player) => player.id === match.serverPlayerId)?.shortName ?? ''} 发球`
          : '发球方暂未提供'}
      </p>
    </div>
  )
}

export function FeaturedMatchSection({
  phase,
  match,
  state,
  onAsk,
}: {
  phase: ProductPhase
  match: MatchViewModel | null
  state: SlateState
  onAsk: () => void
}) {
  return (
    <section aria-labelledby="featured-match-title">
      <Card data-tone="featured">
        <CardHeader className="border-b">
          <div className="flex items-center gap-2 text-primary">
            <Star aria-hidden="true" className="size-4 fill-current" />
            <CardTitle>
              <h2 id="featured-match-title">Featured Match</h2>
            </CardTitle>
          </div>
          <p className="text-sm text-muted-foreground">
            {match ? `${match.tournament} · ${match.round} · ${match.surface}` : '由 Tennix 结构化数据驱动'}
          </p>
          <CardAction>
            {match?.visualStatus === 'live' ? (
              <Badge variant="destructive" role="status">
                <span className="live-pulse size-1.5 rounded-full bg-current" aria-hidden="true" />
                直播
              </Badge>
            ) : match?.visualStatus === 'upcoming' ? (
              <Badge variant="outline" role="status">即将开始</Badge>
            ) : match ? (
              <Badge variant="secondary" role="status">状态待确认</Badge>
            ) : null}
          </CardAction>
        </CardHeader>

        {match ? (
          <>
            <CardContent className="grid items-center gap-5 py-2 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,1.15fr)_minmax(0,1fr)]">
              <FeaturedPlayer
                player={match.players[0]}
                serving={match.serverPlayerId === match.players[0].id}
                align="left"
                isLive={match.visualStatus === 'live'}
              />
              {match.visualStatus === 'live' && match.score ? (
                <FeaturedScore match={match} />
              ) : (
                <div className="flex min-h-40 flex-col items-center justify-center gap-2 rounded-xl bg-background/45 p-4 text-center">
                  <Clock3 aria-hidden="true" className="size-4 text-primary" />
                  <p className="font-mono text-3xl font-semibold tabular-nums">{match.scheduledTime}</p>
                  <p className="text-sm text-muted-foreground">{match.scheduledDate} · {match.timezoneLabel}</p>
                  <Badge variant="secondary">{match.format}</Badge>
                </div>
              )}
              <FeaturedPlayer
                player={match.players[1]}
                serving={match.serverPlayerId === match.players[1].id}
                align="right"
                isLive={match.visualStatus === 'live'}
              />
            </CardContent>

            <CardFooter className="flex-col justify-between gap-3 sm:flex-row">
              <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                {match.visualStatus === 'live' ? (
                  <>
                    <span>{match.freshnessLabel}</span>
                    <span aria-hidden="true">·</span>
                    <span>{match.surface}</span>
                    <span aria-hidden="true">·</span>
                    <span className="text-primary">
                      {match.serverPlayerId
                        ? `${match.players.find((player) => player.id === match.serverPlayerId)?.shortName ?? ''} 发球`
                        : '发球方暂未提供'}
                    </span>
                  </>
                ) : (
                  <>
                    <span>{match.scheduledDate} {match.scheduledTime}</span>
                    <span aria-hidden="true">·</span>
                    <span>{match.surface}</span>
                    <span aria-hidden="true">·</span>
                    <span>{match.tournament} {match.round}</span>
                  </>
                )}
                {phase === 'p2' ? <Badge variant="outline">实时洞察已连接</Badge> : null}
              </div>
              <div className="flex w-full gap-2 sm:w-auto">
                <Link
                  href={`/matches/${encodeURIComponent(match.id)}`}
                  className={cn(buttonVariants({ variant: 'outline' }), 'flex-1 sm:flex-none')}
                >
                  打开比赛
                  <ArrowRight data-icon="inline-end" aria-hidden="true" />
                </Link>
                <Button className="flex-1 sm:flex-none" onClick={onAsk}>
                  <Sparkles data-icon="inline-start" aria-hidden="true" />
                  {match.visualStatus === 'live' ? '实时洞察' : '询问赛程'}
                </Button>
              </div>
            </CardFooter>
          </>
        ) : (
          <CardContent className="py-10">
            <div className="flex min-h-40 flex-col items-center justify-center gap-2 rounded-xl bg-background/45 p-4 text-center">
              <Clock3 aria-hidden="true" className="size-4 text-primary" />
              <p className="text-sm text-muted-foreground">
                {state === 'loading' ? '正在加载重点比赛…' : '当前没有正在直播或即将开始的比赛'}
              </p>
            </div>
          </CardContent>
        )}
      </Card>
    </section>
  )
}

function CompactLiveCard({ match }: { match: HomeMatchViewModel }) {
  return (
    <Link
      href={match.href}
      className="group min-w-64 rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:min-w-0"
      aria-label={`打开 ${match.players[0]} 对阵 ${match.players[1]}`}
    >
      <Card size="sm" className="h-full transition-transform group-hover:-translate-y-0.5 group-hover:ring-primary/35">
        <CardHeader>
          <CardTitle>
            <h3 className="text-sm">{match.tournament}</h3>
          </CardTitle>
          <p className="text-xs text-muted-foreground">{match.round}</p>
          <CardAction>
            <Badge variant="destructive">LIVE</Badge>
          </CardAction>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {match.score
            ? match.score.rows.map((row) => (
                <div key={row.player} className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-2 border-t py-2 first:border-t-0">
                  <div className="flex min-w-0 items-center gap-2">
                    {row.serving ? <span className="size-1.5 shrink-0 rounded-full bg-primary" aria-label="发球方" /> : <span className="size-1.5 shrink-0" aria-hidden="true" />}
                    <span className="truncate text-sm font-medium">{row.player}</span>
                  </div>
                  <span className="font-mono text-sm font-semibold">{row.sets.join(' ')}</span>
                  <span className="min-w-6 text-right font-mono font-semibold text-primary">{row.points}</span>
                </div>
              ))
            : match.players.map((player) => (
                <div key={player} className="flex min-w-0 items-center gap-2 border-t py-2 first:border-t-0">
                  <span className="size-1.5 shrink-0" aria-hidden="true" />
                  <span className="truncate text-sm font-medium">{player}</span>
                </div>
              ))}
          <div className="flex items-center justify-between gap-3 border-t pt-3 text-xs text-muted-foreground">
            <span>{match.freshnessLabel}</span>
            <span>{match.isStale ? '数据较旧' : match.time}</span>
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}

export function LiveNowSection({
  matches,
  state,
  errorCode,
  onRefresh,
}: {
  matches: HomeMatchViewModel[]
  state: SlateState
  errorCode?: string | null
  onRefresh: () => void
}) {
  const scrollerRef = useRef<HTMLDivElement>(null)

  return (
    <section id="live" className="flex scroll-mt-24 flex-col gap-4" aria-labelledby="live-title">
      <SectionHeading
        headingId="live-title"
        eyebrow="LIVE NOW"
        title="正在直播"
        description="比分、发球方与比赛状态来自 Tennix 结构化数据。"
        action={
          <span className="flex items-center gap-2">
            <Button
              variant="outline"
              size="icon-sm"
              aria-label="刷新比赛数据"
              onClick={onRefresh}
            >
              <RefreshCw aria-hidden="true" />
            </Button>
            <Button
              variant="outline"
              size="icon-sm"
              aria-label="查看下一场直播"
              onClick={() => scrollerRef.current?.scrollBy({ left: 280, behavior: 'smooth' })}
            >
              <ArrowRight aria-hidden="true" />
            </Button>
          </span>
        }
      />
      {state === 'loading' ? (
        <p className="rounded-xl border border-dashed bg-muted/15 p-5 text-sm text-muted-foreground">
          正在加载直播比赛…
        </p>
      ) : state === 'error' ? (
        <SlateSectionError title="直播比赛" code={errorCode} onRetry={onRefresh} />
      ) : matches.length === 0 ? (
        <p className="rounded-xl border border-dashed bg-muted/15 p-5 text-sm text-muted-foreground">
          暂无直播比赛
        </p>
      ) : (
        <div ref={scrollerRef} className="grid auto-cols-[minmax(16rem,1fr)] grid-flow-col gap-3 overflow-x-auto pb-1 lg:grid-cols-3 lg:grid-flow-row">
          {matches.map((match) => <CompactLiveCard key={match.id} match={match} />)}
        </div>
      )}
    </section>
  )
}

export function UpcomingSection({
  matches,
  state,
  errorCode,
  onRefresh,
}: {
  matches: HomeMatchViewModel[]
  state: SlateState
  errorCode?: string | null
  onRefresh: () => void
}) {
  return (
    <section id="upcoming" className="flex scroll-mt-24 flex-col gap-4" aria-labelledby="upcoming-title">
      <SectionHeading
        headingId="upcoming-title"
        eyebrow="TONIGHT"
        title="今晚比赛"
        description="已换算为澳门本地时间。"
        action={
          <Link href="#upcoming" className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-foreground">
            查看完整赛程
            <ArrowRight aria-hidden="true" className="size-4" />
          </Link>
        }
      />
      {state === 'loading' ? (
        <p className="rounded-xl border border-dashed bg-muted/15 p-5 text-sm text-muted-foreground">
          正在加载今晚赛程…
        </p>
      ) : state === 'error' ? (
        <SlateSectionError title="今晚赛程" code={errorCode} onRetry={onRefresh} />
      ) : matches.length === 0 ? (
        <p className="rounded-xl border border-dashed bg-muted/15 p-5 text-sm text-muted-foreground">
          今晚暂无待开赛比赛
        </p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {matches.map((match) => (
            <Link
              key={match.id}
              href={match.href}
              className="group rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Card size="sm" className="h-full transition-transform group-hover:-translate-y-0.5 group-hover:ring-primary/35">
                <CardHeader>
                  <CardTitle>
                    <h3 className="text-sm">{match.tournament}</h3>
                  </CardTitle>
                  <p className="text-xs text-muted-foreground">{match.round}</p>
                  <CardAction>
                    <Badge variant="outline">
                      <Clock3 data-icon="inline-start" aria-hidden="true" />
                      {match.time}
                    </Badge>
                  </CardAction>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  {match.players.map((player) => (
                    <div key={player} className="flex min-w-0 items-center gap-2">
                      <span className="truncate font-medium">{player}</span>
                    </div>
                  ))}
                  <div className="flex items-center justify-between gap-3 border-t pt-3 text-xs text-muted-foreground">
                    <span>{match.surface}</span>
                    <ArrowRight aria-hidden="true" className="size-4 text-foreground" />
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </section>
  )
}

export function SlateErrorPanel({
  code,
  onRetry,
}: {
  code: string
  onRetry: () => void
}) {
  return (
    <Card>
      <CardContent className="flex flex-col items-start gap-3 py-8">
        <p className="text-sm font-medium">比赛数据加载失败（{code}）</p>
        <p className="text-sm text-muted-foreground">
          数据服务暂时不可用，请稍后重试；页面不会自动轮询。
        </p>
        <Button variant="outline" onClick={onRetry} aria-label="重试加载比赛数据">
          <RefreshCw data-icon="inline-start" aria-hidden="true" />
          重试加载
        </Button>
      </CardContent>
    </Card>
  )
}
