import Link from 'next/link'
import { ArrowRight, CheckCircle2, Clock3, Radio } from 'lucide-react'

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
import type { HomeMatchViewModel } from '@/lib/view-models'
import { cn } from '@/lib/utils'

export const statusDetails = {
  upcoming: { label: '即将开始', variant: 'outline' as const },
  live: { label: '直播', variant: 'destructive' as const },
  finished: { label: '已完赛', variant: 'secondary' as const },
  unavailable: { label: '状态待确认', variant: 'outline' as const },
}

export function MatchResultCard({
  match,
  onFollowUp,
}: {
  match: HomeMatchViewModel
  onFollowUp: (match: HomeMatchViewModel) => void
}) {
  const status = statusDetails[match.status]

  return (
    <Card size="sm" className="bg-background/45" data-testid={`home-match-${match.status}`}>
      <CardHeader className="border-b">
        <CardTitle>
          <h3 className="text-pretty text-base">
            {match.players[0]} <span className="text-muted-foreground">vs</span> {match.players[1]}
          </h3>
        </CardTitle>
        <p className="text-xs text-muted-foreground">{match.tournament} · {match.round}</p>
        <CardAction>
          <Badge variant={status.variant} role="status">
            {match.status === 'live' ? (
              <span className="live-pulse size-1.5 rounded-full bg-current" aria-hidden="true" />
            ) : null}
            {status.label}
          </Badge>
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {match.score ? (
          <div className="rounded-lg bg-muted/25 p-3">
            <div className="mb-2 flex items-center justify-between gap-3 text-xs text-muted-foreground">
              <span className={cn('flex items-center gap-1.5', match.status === 'live' && 'text-live')}>
                <Radio aria-hidden="true" className="size-3.5" />
                {match.status === 'live' ? '实时比分' : '比分'}
              </span>
              <span>{match.freshnessLabel}</span>
            </div>
            <div className="flex flex-col gap-2">
              {match.score.rows.map((row) => (
                <div key={row.player} className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-3">
                  <span className="flex min-w-0 items-center gap-2 font-medium">
                    {row.serving ? <span className="size-1.5 shrink-0 rounded-full bg-primary" aria-label="发球方" /> : null}
                    <span className="truncate">{row.player}</span>
                  </span>
                  <span className="font-mono text-sm text-muted-foreground tabular-nums">{row.sets.join('  ')}</span>
                  <span className="min-w-7 text-right font-mono text-lg font-semibold text-primary tabular-nums">{row.points}</span>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-xs">
          <div>
            <dt className="text-muted-foreground">时间</dt>
            <dd className="mt-1 flex items-center gap-1.5 font-medium">
              <Clock3 aria-hidden="true" className="size-3.5 text-primary" />
              {match.time}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">场地</dt>
            <dd className="mt-1 font-medium">{match.surface}</dd>
          </div>
          <div className="col-span-2">
            <dt className="text-muted-foreground">数据新鲜度</dt>
            <dd className="mt-1 flex items-center gap-1.5 font-medium">
              <CheckCircle2 aria-hidden="true" className="size-3.5 text-primary" />
              {match.freshnessLabel}
            </dd>
          </div>
        </dl>
      </CardContent>

      <CardFooter className="flex-col gap-2 sm:flex-row">
        <Link
          href={match.href}
          className={cn(buttonVariants(), 'w-full sm:flex-1')}
          aria-label={`打开比赛：${match.players[0]} 对阵 ${match.players[1]}`}
        >
          打开比赛
          <ArrowRight data-icon="inline-end" aria-hidden="true" />
        </Link>
        <Button variant="outline" className="w-full sm:flex-1" onClick={() => onFollowUp(match)}>
          继续追问
        </Button>
      </CardFooter>
    </Card>
  )
}
