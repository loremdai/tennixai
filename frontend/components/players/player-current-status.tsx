import Link from 'next/link'
import { CalendarClock, ChevronRight, CircleDot, Info } from 'lucide-react'

import { PlayerCountry } from '@/components/player-country'
import type { PlayerCurrentStatusPreview } from '@/components/players/player-preview-data'
import { Badge } from '@/components/ui/badge'
import { buttonVariants } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { cn } from '@/lib/utils'

export function PlayerCurrentStatus({
  status,
  profileName,
}: {
  status: PlayerCurrentStatusPreview
  profileName: string
}) {
  if (status.kind === 'none') {
    return (
      <Card aria-labelledby="current-status-title">
        <CardHeader>
          <CardTitle><h2 id="current-status-title">当前比赛状态</h2></CardTitle>
        </CardHeader>
        <CardContent className="flex min-h-40 flex-col items-center justify-center gap-3 text-center">
          <span className="flex size-11 items-center justify-center rounded-full bg-muted text-muted-foreground">
            <Info aria-hidden="true" className="size-5" />
          </span>
          <div className="flex max-w-sm flex-col gap-1">
            <p className="font-medium">暂无比赛信息</p>
            <p className="text-sm leading-relaxed text-muted-foreground">{status.message}</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  const isLive = status.kind === 'live'
  return (
    <Card aria-labelledby="current-status-title" className={isLive ? 'bg-primary/[0.04] ring-primary/25' : undefined}>
      <CardHeader>
        <div>
          <CardTitle><h2 id="current-status-title">当前比赛状态</h2></CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">{status.event} · {status.round}</p>
        </div>
        <Badge variant="outline" className={isLive ? 'border-live/30 bg-live/10 text-live' : 'border-primary/25 bg-primary/10 text-primary'}>
          {isLive ? (
            <><CircleDot data-icon="inline-start" aria-hidden="true" />LIVE</>
          ) : (
            <><CalendarClock data-icon="inline-start" aria-hidden="true" />下一场</>
          )}
        </Badge>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="rounded-xl bg-background/80 p-4 ring-1 ring-foreground/10">
          <p className="text-xs text-muted-foreground">对手</p>
          <div className="mt-2 flex items-center gap-2">
            <PlayerCountry player={status.opponent} />
            <div className="min-w-0">
              <p className="truncate font-medium">{status.opponent.name}</p>
              {status.opponent.nameZh ? <p className="text-xs text-muted-foreground">{status.opponent.nameZh}</p> : null}
            </div>
          </div>
        </div>
        {isLive ? (
          <div>
            <p className="font-mono text-2xl font-semibold tabular-nums">{status.score}</p>
            <p className="mt-1 text-xs text-muted-foreground">{status.detail} · {status.freshness}</p>
          </div>
        ) : (
          <div>
            <p className="font-mono text-2xl font-semibold tabular-nums">{status.startLabel}</p>
            <p className="mt-1 text-xs text-muted-foreground">{status.countdown}</p>
          </div>
        )}
      </CardContent>
      <CardFooter>
        <Link
          href={`/match?status=${status.kind === 'live' ? 'live' : 'upcoming'}`}
          aria-label={`查看 ${profileName} 的${isLive ? '实时比赛' : '下一场比赛'}`}
          className={cn(buttonVariants({ variant: isLive ? 'default' : 'outline', size: 'lg' }), 'w-full')}
        >
          查看比赛详情
          <ChevronRight data-icon="inline-end" aria-hidden="true" />
        </Link>
      </CardFooter>
    </Card>
  )
}
