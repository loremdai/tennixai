import Link from 'next/link'
import { ArrowRight } from 'lucide-react'

import { DecisionStatusBadge } from '@/components/p3/decision-status'
import { PlayerAvatar } from '@/components/player-avatar'
import type { DecisionOverlay, DecisionState } from '@/components/p3/p3-preview-data'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import type {
  DecisionActionValue,
  ModelAvailabilitySummaryValue,
  QuoteStateValue,
} from '@/lib/api/types'

export type MarketRowData = {
  id: string
  match: string
  tournament: string
  tierLabel: string
  phase: 'live' | 'upcoming' | 'closed' | 'unknown'
  modelAvailability: ModelAvailabilitySummaryValue
  modelAvailabilityLabel: string | null
  decisionAction: DecisionActionValue | null
  quoteState: QuoteStateValue
  quoteLabel: string
  playerOne: string
  playerTwo: string
  playerImages?: [string | null, string | null] | null
  playerOneAsk: number | null
  playerTwoAsk: number | null
  spread: number | null
  depth: number | null
  modelProbability: number | null
  reason: string | null
  freshness: string
  stale: boolean
  overlay?: DecisionOverlay
  href: string | null
}

function formatPercent(value: number | null): string {
  if (value === null) return '—'
  return `${(value * 100).toFixed(1)}%`
}

const phaseLabels: Record<MarketRowData['phase'], string> = {
  live: '直播',
  upcoming: '即将开始',
  closed: '已结束',
  unknown: '状态未知',
}

export function MarketRow({ market }: { market: MarketRowData }) {
  const overlay = market.overlay ?? (market.stale ? 'stale' : 'none')
  const modelProbabilityLabel = market.playerOne === '—'
    ? '模型估算胜率'
    : `${market.playerOne} 模型胜率`
  // A decision badge only ever comes from a real observation; without one
  // the row states its quote state instead of inventing MARKET_ONLY.
  const decision = market.decisionAction
  const note = market.reason ?? market.modelAvailabilityLabel
  const card = (
    <Card size="sm" className="transition-[transform,box-shadow] group-hover:-translate-y-0.5 group-hover:ring-primary/35">
      <CardContent className="grid min-h-28 grid-cols-2 items-center gap-4 py-1 md:grid-cols-[minmax(15rem,1.5fr)_minmax(11rem,0.9fr)_minmax(8rem,0.65fr)_minmax(11rem,1fr)_auto]">
        <div className="col-span-2 min-w-0 md:col-span-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate font-semibold">{market.match}</h3>
            <Badge variant="outline">{phaseLabels[market.phase]}</Badge>
            <Badge variant="secondary">{market.tierLabel}</Badge>
          </div>
          <p className="mt-1 truncate text-sm text-muted-foreground">{market.tournament}</p>
          {note ? <p className="mt-2 text-xs text-muted-foreground">{note}</p> : null}
        </div>

        <dl className="grid grid-cols-2 gap-3 rounded-lg bg-muted/30 p-3">
          <div>
            <dt className="flex min-w-0 items-center gap-2 truncate text-xs text-muted-foreground">
              <PlayerAvatar name={market.playerOne} imageUrl={market.playerImages?.[0]} className="size-7" />
              <span className="truncate">{market.playerOne} 胜出报价</span>
            </dt>
            <dd className="mt-1 font-mono text-lg font-semibold tabular-nums">{formatPercent(market.playerOneAsk)}</dd>
          </div>
          <div>
            <dt className="flex min-w-0 items-center gap-2 truncate text-xs text-muted-foreground">
              <PlayerAvatar name={market.playerTwo} imageUrl={market.playerImages?.[1]} className="size-7" />
              <span className="truncate">{market.playerTwo} 胜出报价</span>
            </dt>
            <dd className="mt-1 font-mono text-lg font-semibold tabular-nums">{formatPercent(market.playerTwoAsk)}</dd>
          </div>
        </dl>

        <dl>
          <dt className="text-xs text-muted-foreground">{modelProbabilityLabel}</dt>
          <dd className="mt-1 font-mono text-lg font-semibold tabular-nums">{formatPercent(market.modelProbability)}</dd>
          {market.modelAvailabilityLabel ? (
            <dd className="mt-1 text-xs text-muted-foreground">{market.modelAvailabilityLabel}</dd>
          ) : null}
        </dl>

        <dl className="grid grid-cols-2 gap-3">
          <div><dt className="text-xs text-muted-foreground" title="每位球员都同时有买入价和卖出价时，才计入平均值。">平均价差</dt><dd className="mt-1 font-mono font-semibold">{formatPercent(market.spread)}</dd></div>
          <div><dt className="text-xs text-muted-foreground" title="双方买卖盘最优一档的金额合计，不代表整个盘口，也不保证全部可成交。">最优档金额</dt><dd className="mt-1 font-mono font-semibold">{market.depth === null ? '—' : `$${market.depth.toLocaleString('en-US', { maximumFractionDigits: 2 })}`}</dd></div>
          <div className="col-span-2"><dt className="sr-only">报价更新时间</dt><dd className={cn('text-xs text-muted-foreground', market.stale && 'text-destructive')}>{market.freshness}</dd></div>
        </dl>

        <div className="flex items-center justify-between gap-2 md:justify-end">
          {decision !== null ? (
            <DecisionStatusBadge state={decision as DecisionState} overlay={overlay} />
          ) : (
            <Badge variant="outline" data-quote-state={market.quoteState}>
              {market.quoteLabel}
            </Badge>
          )}
          {market.href !== null ? (
            <ArrowRight aria-hidden="true" className="size-4 shrink-0 text-foreground transition-transform group-hover:translate-x-0.5" />
          ) : null}
        </div>
      </CardContent>
    </Card>
  )

  if (market.href === null) {
    // Unmapped market-only rows are not navigable; the card stays visible
    // without inventing a destination.
    return (
      <div className="group rounded-xl" aria-label={`${market.match} 市场报价`}>
        {card}
      </div>
    )
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
