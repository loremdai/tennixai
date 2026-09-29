import Link from 'next/link'

import { DecisionStatusBadge } from '@/components/p3/decision-status'
import { PlayerName } from '@/components/player-name'
import type { DecisionOverlay, DecisionState } from '@/components/p3/p3-preview-data'
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
  playerLocalizedNames?: [string | null, string | null] | null
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

function quoteStatus(market: MarketRowData): string {
  if (market.quoteState === 'stale') return market.freshness
  if (market.quoteLabel.includes(' · ')) return market.quoteLabel
  return `${market.quoteLabel} · ${market.freshness.replace(/^上次有效报价 · /, '')}`
}

const phaseLabels: Record<MarketRowData['phase'], string> = {
  live: '进行中',
  upcoming: '未开始',
  closed: '已结束',
  unknown: '状态未知',
}

export function MarketRow({ market }: { market: MarketRowData }) {
  const overlay = market.overlay ?? (market.stale ? 'stale' : 'none')
  const decision = market.decisionAction
  const card = (
    <Card size="sm" className="border-foreground/10 bg-[linear-gradient(105deg,#0d241a,#071811)] transition-colors group-hover:border-primary/35">
      <CardContent className="grid gap-3 py-2 lg:grid-cols-[minmax(0,1.05fr)_minmax(20rem,1fr)_minmax(13rem,0.72fr)] lg:items-center lg:gap-5 lg:px-5 lg:py-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
            <p className="break-words text-muted-foreground">{market.tournament}</p>
            <span className="inline-flex items-center gap-1.5 text-muted-foreground">
              <span
                className={cn('size-2 shrink-0 rounded-full bg-muted-foreground', market.phase === 'live' && 'bg-live')}
                aria-hidden="true"
              />
              {phaseLabels[market.phase]}
            </span>
          </div>
          <h3 className="mt-2 break-words text-lg font-semibold leading-snug md:text-xl">
            {market.match}
          </h3>
        </div>

        <section className="min-w-0" aria-label="胜出买入参考价">
          <h4 className="mb-2 text-sm text-muted-foreground">胜出买入参考价</h4>
          <dl className="grid min-w-0 grid-cols-2 gap-2 md:gap-2.5">
            {[market.playerOne, market.playerTwo].map((name, index) => (
              <div key={`${index}-${name}`} className="min-w-0 rounded-lg border border-foreground/10 bg-muted/20 px-2.5 py-2 text-center md:px-3">
                <dt className="break-words text-xs font-medium leading-snug text-foreground sm:text-sm">
                  {name !== '—' ? (
                    <PlayerName
                      name={name}
                      localizedName={market.playerLocalizedNames?.[index]}
                      className="w-full min-w-0 max-w-full"
                      primaryClassName="break-words text-clip overflow-visible whitespace-normal"
                      secondaryClassName="break-words text-clip overflow-visible whitespace-normal"
                    />
                  ) : '—'}
                </dt>
                <dd className="mt-1.5 font-mono text-xl font-semibold tabular-nums md:text-2xl">
                  {formatPercent(index === 0 ? market.playerOneAsk : market.playerTwoAsk)}
                </dd>
              </div>
            ))}
          </dl>
        </section>

        <div className="grid min-w-0 gap-2 pt-1 lg:border-l lg:py-1 lg:pl-5 lg:pt-0">
          <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted-foreground">
            <p className="inline-flex min-w-0 items-center gap-1.5" data-quote-state={market.quoteState}>
              <span className={cn('size-2 shrink-0 rounded-full bg-muted-foreground', market.stale && 'bg-destructive')} aria-hidden="true" />
              {quoteStatus(market)}
            </p>
            {decision !== null ? (
              <DecisionStatusBadge state={decision as DecisionState} overlay={overlay} />
            ) : null}
          </div>
          <dl className="grid min-w-0 grid-cols-2 gap-x-3 gap-y-3">
            {market.spread !== null ? (
              <div>
                <dt className="text-xs text-muted-foreground" title="每位球员都同时有买入价和卖出价时，才计入平均值。">
                  平均价差
                </dt>
                <dd className="mt-1 font-mono font-semibold tabular-nums">{formatPercent(market.spread)}</dd>
              </div>
            ) : null}
            {market.depth !== null ? (
              <div className="border-l border-foreground/10 pl-3 md:pl-4">
                <dt className="text-xs text-muted-foreground" title="双方买卖盘最优一档的金额合计，不代表整个盘口，也不保证全部可成交。">
                  最优档金额
                </dt>
                <dd className="mt-1 font-mono font-semibold tabular-nums">
                  ${market.depth.toLocaleString('en-US', { maximumFractionDigits: 2 })}
                </dd>
              </div>
            ) : null}
            {market.modelProbability !== null ? (
              <div className="min-w-0">
                <dt className="break-words text-xs text-muted-foreground">
                  {market.playerOne === '—' ? '模型估算胜率' : `${market.playerOne} 模型胜率`}
                </dt>
                <dd className="mt-1 font-mono font-semibold tabular-nums">
                  {formatPercent(market.modelProbability)}
                </dd>
              </div>
            ) : null}
          </dl>
          {decision !== null && market.reason ? (
            <p className="break-words text-xs leading-relaxed text-muted-foreground">
              {market.reason}
            </p>
          ) : null}
        </div>
      </CardContent>
    </Card>
  )

  if (market.href === null) {
    return (
      <div className="rounded-xl" aria-label={`${market.match} 市场报价`}>
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
