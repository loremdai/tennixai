import Link from 'next/link'
import { ChevronRight } from 'lucide-react'

import { PlayerAvatar } from '@/components/player-avatar'
import { PlayerName } from '@/components/player-name'
import { Card, CardContent } from '@/components/ui/card'
import type { MarketRowModel } from '@/lib/p3-view-models'
import { cn } from '@/lib/utils'

function formatCents(value: number | null): string {
  if (value === null) return '—'
  return `${(value * 100).toFixed(1).replace(/\.0$/, '')}¢`
}

function quoteStatus(market: MarketRowModel): string {
  if (market.quoteState === 'realtime') return '实时报价'
  if (market.quoteState === 'stale') return market.freshness
  if (market.quoteLabel.includes(' · ')) return market.quoteLabel
  return `${market.quoteLabel} · ${market.freshness.replace(/^上次有效报价 · /, '')}`
}

const phaseLabels: Record<MarketRowModel['phase'], string> = {
  live: '进行中',
  upcoming: '赛前',
  closed: '已结束',
  unknown: '状态未知',
}

const scheduledTimeFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

function matchContextDetail(market: MarketRowModel): string | null {
  const context = market.matchContext
  if (!context) return null

  if (
    market.phase === 'live' &&
    context.matchStatus === 'live' &&
    context.liveStateCurrent &&
    context.currentSetNumber !== null
  ) {
    return `第 ${context.currentSetNumber} 盘`
  }

  if (market.phase === 'upcoming' && context.scheduledAt) {
    const scheduledAt = new Date(context.scheduledAt)
    return Number.isNaN(scheduledAt.getTime())
      ? null
      : scheduledTimeFormatter.format(scheduledAt)
  }

  if (
    market.phase === 'closed' &&
    context.matchStatus === 'finished' &&
    context.score
  ) {
    const sets = context.score.sets
      .filter(
        (set) => set.player1_games !== null && set.player2_games !== null,
      )
      .map((set) => `${set.player1_games}–${set.player2_games}`)
    return sets.length > 0 ? sets.join(', ') : null
  }

  return null
}

export function MarketRow({ market }: { market: MarketRowModel }) {
  const players = [market.playerOne, market.playerTwo] as const
  const asks = [market.playerOneAsk, market.playerTwoAsk] as const
  const contextDetail = matchContextDetail(market)
  const card = (
    <Card
      size="sm"
      className="border-foreground/10 bg-card/55 transition-colors group-hover:border-primary/35"
    >
      <CardContent className="grid gap-3 py-3 sm:gap-4 lg:grid-cols-[minmax(13rem,1fr)_minmax(18rem,1.3fr)_minmax(8rem,0.55fr)_minmax(8rem,0.5fr)] lg:items-center lg:px-5 lg:py-3">
        <div className="min-w-0 lg:border-r lg:pr-4">
          <p className="break-words text-sm font-medium text-foreground">
            <span className="text-primary">{market.tierLabel}</span>
            <span className="px-2 text-muted-foreground" aria-hidden="true">·</span>
            {market.tournament}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
            <span
              className={cn(
                'inline-flex items-center rounded-lg border px-2.5 py-1 text-xs font-medium',
                market.phase === 'live'
                  ? 'border-primary/45 text-primary'
                  : 'border-foreground/10 text-muted-foreground',
              )}
            >
              {phaseLabels[market.phase]}
            </span>
            {contextDetail ? (
              <span className="text-sm text-muted-foreground">{contextDetail}</span>
            ) : null}
          </div>
          {players.every((name) => name === '—') ? (
            <p className="mt-2 break-words text-sm font-semibold">{market.match}</p>
          ) : null}
        </div>

        <section className="min-w-0" aria-label="参赛球员">
          {players.map((name, index) => (
            <div
              key={`${index}-${name}`}
              className={cn(
                'flex min-w-0 items-center gap-3 py-1.5',
                index === 0 && 'border-b border-foreground/10',
              )}
            >
              <PlayerAvatar
                name={name === '—' ? `第${index + 1}位球员` : name}
                imageUrl={market.playerImages?.[index]}
                className="size-9 border border-foreground/15 bg-background"
              />
              {name === '—' ? (
                <span className="text-sm text-muted-foreground">—</span>
              ) : (
                <PlayerName
                  name={name}
                  localizedName={market.playerLocalizedNames?.[index]}
                  className="w-full min-w-0"
                  primaryClassName="!overflow-visible !text-clip !whitespace-normal break-words text-sm font-semibold text-foreground [overflow-wrap:anywhere]"
                  secondaryClassName="mt-0.5 !overflow-visible !text-clip !whitespace-normal break-words text-xs text-muted-foreground [overflow-wrap:anywhere]"
                />
              )}
            </div>
          ))}
        </section>

        <dl className="grid min-w-0 gap-2 lg:border-l lg:pl-4">
          {asks.map((ask, index) => (
            <div
              key={index}
              className="flex min-h-10 items-center justify-center rounded-lg border border-foreground/10 bg-background/55 px-3 py-1.5 text-center"
            >
              <dt className="sr-only">{players[index]} 买入参考价</dt>
              <dd className="font-mono text-lg font-semibold tabular-nums text-primary sm:text-xl">
                {formatCents(ask)}
              </dd>
            </div>
          ))}
        </dl>

        <div className="flex min-w-0 items-center justify-between gap-2 border-t border-foreground/10 pt-3 text-sm text-muted-foreground lg:h-full lg:border-l lg:border-t-0 lg:pl-4 lg:pt-0">
          <p
            className="inline-flex min-w-0 items-center gap-2"
            data-quote-state={market.quoteState}
          >
            <span
              className={cn(
                'size-2 shrink-0 rounded-full',
                market.quoteState === 'realtime' && !market.stale
                  ? 'bg-primary'
                  : market.stale
                    ? 'bg-destructive'
                    : 'bg-muted-foreground',
              )}
              aria-hidden="true"
            />
            <span className="break-words">{quoteStatus(market)}</span>
          </p>
          <ChevronRight aria-hidden="true" className="size-5 shrink-0 text-foreground" />
        </div>
      </CardContent>
    </Card>
  )

  if (market.href === null) {
    return <div className="rounded-xl" aria-label={`${market.match} 市场报价`}>{card}</div>
  }
  return (
    <Link
      href={market.href}
      className="group rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-ring"
      aria-label={`查看 ${market.match} 市场`}
    >
      {card}
    </Link>
  )
}
