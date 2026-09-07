'use client'

import { useRef } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import {
  ArrowRight,
  Clock3,
  Radio,
  Sparkles,
  Star,
} from 'lucide-react'

import { SectionHeading } from '@/components/home/section-heading'
import {
  featuredMatch,
  liveMatches,
  upcomingMatches,
  type LiveMatch,
  type MatchPlayer,
} from '@/components/home/home-data'
import type { ProductPhase } from '@/components/match/match-data'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
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
import { cn } from '@/lib/utils'

function Flag({ src, country }: { src: string; country: string }) {
  return (
    <img
      src={src}
      alt={`${country}国旗`}
      width={20}
      height={14}
      loading="lazy"
      className="h-3.5 w-5 rounded-sm object-cover ring-1 ring-border"
    />
  )
}

function FeaturedPlayer({
  player,
  portrait,
  align,
  isLive,
}: {
  player: MatchPlayer
  portrait: string
  align: 'left' | 'right'
  isLive: boolean
}) {
  return (
    <div className={cn('flex items-center gap-3', align === 'right' && 'flex-row-reverse text-right')}>
      <Avatar className="size-12">
        <AvatarImage src={portrait} alt={`${player.name} 球员肖像`} />
        <AvatarFallback>{player.shortName.slice(0, 2)}</AvatarFallback>
      </Avatar>
      <div className="min-w-0">
        <div className={cn('flex items-center gap-2', align === 'right' && 'justify-end')}>
          <Flag src={player.flagUrl} country={player.country} />
          <Badge variant="outline">#{player.rank}</Badge>
        </div>
        <h3 className="mt-2 text-balance text-base font-semibold leading-tight tracking-tight">{player.name}</h3>
        <p className="mt-1 text-sm text-muted-foreground">世界排名 #{player.rank}</p>
        {isLive ? (
          player.serving ? (
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

function FeaturedScore({ match }: { match: LiveMatch }) {
  return (
    <div className="flex flex-col gap-3 rounded-xl bg-background/45 p-4">
      <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
        <span>{match.currentSet}</span>
        <span className="font-mono">{match.elapsed}</span>
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)_repeat(3,2rem)] items-center gap-3 text-center">
        <span className="text-left text-xs text-muted-foreground">球员</span>
        <span className="font-mono text-xs text-muted-foreground">1</span>
        <span className="font-mono text-xs text-muted-foreground">2</span>
        <span className="font-mono text-xs text-muted-foreground">局分</span>
        {match.players.map((player) => (
          <div key={player.name} className="contents">
            <span className="flex min-w-0 items-center gap-2 text-left text-sm font-medium">
              {player.serving ? <span className="size-1.5 shrink-0 rounded-full bg-primary" aria-label="发球方" /> : null}
              <span className="truncate">{player.shortName}</span>
            </span>
            <span className="font-mono text-xl font-semibold tabular-nums">{player.sets[0]}</span>
            <span className="font-mono text-xl font-semibold tabular-nums">{player.sets[1]}</span>
            <span className="font-mono text-2xl font-semibold text-primary tabular-nums">{player.pointScore}</span>
          </div>
        ))}
      </div>
      <p className="border-t pt-3 text-center text-xs text-muted-foreground">
        Sinner 发球 · 第三盘第 10 局
      </p>
    </div>
  )
}

export function FeaturedMatchSection({
  phase,
  onAsk,
}: {
  phase: ProductPhase
  onAsk: () => void
}) {
  const isLive = phase !== 'p1'

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
          <p className="text-sm text-muted-foreground">ATP Finals · Semi-final · Indoor Hard</p>
          <CardAction>
            {isLive ? (
              <Badge variant="destructive" role="status">
                <span className="live-pulse size-1.5 rounded-full bg-current" aria-hidden="true" />
                直播
              </Badge>
            ) : (
              <Badge variant="outline" role="status">即将开始</Badge>
            )}
          </CardAction>
        </CardHeader>

        <CardContent className="grid items-center gap-5 py-2 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,1.15fr)_minmax(0,1fr)]">
          <FeaturedPlayer player={featuredMatch.players[0]} portrait="/images/player-sinner.png" align="left" isLive={isLive} />
          {isLive ? (
            <FeaturedScore match={featuredMatch} />
          ) : (
            <div className="flex min-h-40 flex-col items-center justify-center gap-2 rounded-xl bg-background/45 p-4 text-center">
              <Clock3 aria-hidden="true" className="size-4 text-primary" />
              <p className="font-mono text-3xl font-semibold tabular-nums">20:30</p>
              <p className="text-sm text-muted-foreground">今晚 · 都灵，意大利</p>
              <Badge variant="secondary">赛前简报已就绪</Badge>
            </div>
          )}
          <FeaturedPlayer player={featuredMatch.players[1]} portrait="/images/player-alcaraz.png" align="right" isLive={isLive} />
        </CardContent>

        <CardFooter className="flex-col justify-between gap-3 sm:flex-row">
          <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
            {isLive ? (
              <>
                <span>{featuredMatch.elapsed}</span>
                <span aria-hidden="true">·</span>
                <span>{featuredMatch.currentSet}</span>
                <span aria-hidden="true">·</span>
                <span className="text-primary">Sinner 发球</span>
              </>
            ) : (
              <>
                <span>今晚 20:30</span>
                <span aria-hidden="true">·</span>
                <span>室内硬地</span>
                <span aria-hidden="true">·</span>
                <span>ATP Finals 半决赛</span>
              </>
            )}
            {phase === 'p2' ? <Badge variant="outline">实时洞察已连接</Badge> : null}
          </div>
          <div className="flex w-full gap-2 sm:w-auto">
            <Link href={`/match?status=${isLive ? 'live' : 'upcoming'}`} className={cn(buttonVariants({ variant: 'outline' }), 'flex-1 sm:flex-none')}>
              打开比赛
              <ArrowRight data-icon="inline-end" aria-hidden="true" />
            </Link>
            <Button className="flex-1 sm:flex-none" onClick={onAsk}>
              <Sparkles data-icon="inline-start" aria-hidden="true" />
              {isLive ? '实时洞察' : '询问赛程'}
            </Button>
          </div>
        </CardFooter>
      </Card>
    </section>
  )
}

function CompactLiveCard({ match }: { match: LiveMatch }) {
  return (
    <Link
      href={match.href}
      className="group min-w-64 rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:min-w-0"
      aria-label={`打开 ${match.players[0].name} 对阵 ${match.players[1].name}`}
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
          {match.players.map((player) => (
            <div key={player.name} className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-2 border-t py-2 first:border-t-0">
              <div className="flex min-w-0 items-center gap-2">
                {player.serving ? <span className="size-1.5 shrink-0 rounded-full bg-primary" aria-label="发球方" /> : <span className="size-1.5 shrink-0" aria-hidden="true" />}
                <Flag src={player.flagUrl} country={player.country} />
                <span className="truncate text-sm font-medium">{player.shortName}</span>
              </div>
              <span className="font-mono text-sm font-semibold">{player.sets.join(' ')}</span>
              <span className="min-w-6 text-right font-mono font-semibold text-primary">{player.pointScore}</span>
            </div>
          ))}
          <div className="flex items-center justify-between gap-3 border-t pt-3 text-xs text-muted-foreground">
            <span>{match.currentSet}</span>
            <span>{match.elapsed}</span>
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}

export function LiveNowSection() {
  const scrollerRef = useRef<HTMLDivElement>(null)

  return (
    <section id="live" className="flex scroll-mt-24 flex-col gap-4" aria-labelledby="live-title">
      <SectionHeading
        headingId="live-title"
        eyebrow="LIVE NOW"
        title="正在直播"
        description="比分、发球方与比赛状态实时同步。"
        action={
          <Button
            variant="outline"
            size="icon-sm"
            aria-label="查看下一场直播"
            onClick={() => scrollerRef.current?.scrollBy({ left: 280, behavior: 'smooth' })}
          >
            <ArrowRight aria-hidden="true" />
          </Button>
        }
      />
      <div ref={scrollerRef} className="grid auto-cols-[minmax(16rem,1fr)] grid-flow-col gap-3 overflow-x-auto pb-1 lg:grid-cols-3 lg:grid-flow-row">
        {liveMatches.map((match) => <CompactLiveCard key={match.id} match={match} />)}
      </div>
    </section>
  )
}

export function UpcomingSection() {
  return (
    <section id="upcoming" className="flex scroll-mt-24 flex-col gap-4" aria-labelledby="upcoming-title">
      <SectionHeading
        headingId="upcoming-title"
        eyebrow="TONIGHT"
        title="今晚比赛"
        description="已换算为你的本地时间。"
        action={
          <Link href="#upcoming" className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-foreground">
            查看完整赛程
            <ArrowRight aria-hidden="true" className="size-4" />
          </Link>
        }
      />
      <div className="grid gap-3 sm:grid-cols-2">
        {upcomingMatches.map((match) => (
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
                  <div key={player.name} className="flex min-w-0 items-center gap-2">
                    <Flag src={player.flagUrl} country={player.country} />
                    <span className="truncate font-medium">{player.name}</span>
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
    </section>
  )
}
