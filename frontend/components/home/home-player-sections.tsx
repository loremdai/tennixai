'use client'

import { useState } from 'react'
import {
  Bell,
  BellOff,
  Radio,
} from 'lucide-react'

import { followedPlayers, recentResults } from '@/components/home/home-data'
import { SectionHeading } from '@/components/home/section-heading'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

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

export function FollowedPlayersSection() {
  const [alerts, setAlerts] = useState<Set<string>>(
    () => new Set(followedPlayers.map((player) => player.id)),
  )

  function toggleAlert(playerId: string) {
    setAlerts((current) => {
      const next = new Set(current)
      if (next.has(playerId)) next.delete(playerId)
      else next.add(playerId)
      return next
    })
  }

  return (
    <section id="players" className="flex scroll-mt-24 flex-col gap-4" aria-labelledby="players-title">
      <SectionHeading
        headingId="players-title"
        eyebrow="YOUR WATCHLIST"
        title="关注球员"
        description="下一场与当前比赛状态，一眼掌握。"
        action={<Badge variant="outline">4 位球员</Badge>}
      />
      <div className="grid gap-3 sm:grid-cols-2">
        {followedPlayers.map((player) => {
          const alertEnabled = alerts.has(player.id)
          return (
            <Card key={player.id} size="sm" className="h-full">
              <CardHeader>
                <div className="flex min-w-0 items-center gap-3">
                  <Avatar className="size-11">
                    <AvatarImage src={player.portrait} alt={`${player.name} 球员肖像`} />
                    <AvatarFallback>{player.name.slice(0, 2)}</AvatarFallback>
                  </Avatar>
                  <div className="min-w-0">
                    <CardTitle>
                      <h3 className="truncate text-sm">{player.name}</h3>
                    </CardTitle>
                    <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                      <Flag src={player.flagUrl} country={player.country} />
                      <span>世界 #{player.rank}</span>
                    </div>
                  </div>
                </div>
                <CardAction>
                  {player.live ? (
                    <Badge variant="destructive">
                      <Radio data-icon="inline-start" aria-hidden="true" />
                      LIVE
                    </Badge>
                  ) : (
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label={`${alertEnabled ? '关闭' : '开启'} ${player.name} 比赛提醒`}
                      aria-pressed={alertEnabled}
                      onClick={() => toggleAlert(player.id)}
                    >
                      {alertEnabled ? <Bell aria-hidden="true" /> : <BellOff aria-hidden="true" />}
                    </Button>
                  )}
                </CardAction>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between gap-3 rounded-lg bg-muted/25 p-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{player.status}</p>
                    <p className="mt-1 truncate text-xs text-muted-foreground">{player.detail}</p>
                  </div>
                  <span className={player.live ? 'size-2 shrink-0 rounded-full bg-live' : 'size-2 shrink-0 rounded-full bg-primary'} aria-hidden="true" />
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>
    </section>
  )
}

export function RecentResultsCard() {
  return (
    <Card id="results" className="scroll-mt-24">
      <CardHeader>
        <CardTitle>
          <h2>Recent Results</h2>
        </CardTitle>
        <p className="text-sm text-muted-foreground">近期完赛</p>
        <CardAction>
          <Badge variant="outline">FT</Badge>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col">
        {recentResults.map((result) => (
          <article key={result.id} className="flex flex-col gap-3 border-t py-4 first:border-t-0 first:pt-0 last:pb-0">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-medium">{result.tournament}</p>
                <p className="mt-1 text-[11px] text-muted-foreground">{result.round}</p>
              </div>
              <Badge variant="outline">FT</Badge>
            </div>
            <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-2 text-sm">
              <span className="flex min-w-0 items-center gap-2 font-medium">
                <Flag src={result.winner.flagUrl} country={result.winner.country} />
                <span className="truncate">{result.winner.name}</span>
              </span>
              <span className="font-mono font-semibold text-primary">{result.score}</span>
              <span className="flex min-w-0 items-center gap-2 text-muted-foreground">
                <Flag src={result.loser.flagUrl} country={result.loser.country} />
                <span className="truncate">{result.loser.name}</span>
              </span>
              <span className="font-mono text-xs text-muted-foreground">已完赛</span>
            </div>
          </article>
        ))}
      </CardContent>
    </Card>
  )
}
