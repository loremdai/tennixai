import Link from 'next/link'
import { ArrowRight } from 'lucide-react'

import { DecisionStatusBadge, decisionStateLabels } from '@/components/p3/decision-status'
import { PlayerAvatar } from '@/components/player-avatar'
import { PlayerName } from '@/components/player-name'
import type { DecisionOverlay } from '@/components/p3/p3-preview-data'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'

export type OpportunityRowData = {
  id: string
  match: string
  tournament: string
  phase: 'live' | 'upcoming'
  selection: string
  selectionLocalizedName?: string | null
  playerNames?: [string, string] | null
  playerLocalizedNames?: [string | null, string | null] | null
  selectionImageUrl?: string | null
  modelProbability: number | null
  executableProbability: number | null
  edgePp: number | null
  state: 'buy' | 'wait'
  maxBuyPrice: number | null
  freshness: string
  stale: boolean
  overlay?: DecisionOverlay
  href: string
}

function formatPercent(value: number | null): string {
  if (value === null) return '—'
  return `${(value * 100).toFixed(1)}%`
}

export function OpportunityRow({ opportunity }: { opportunity: OpportunityRowData }) {
  const overlay = opportunity.overlay ?? (opportunity.stale ? 'stale' : 'none')
  return (
    <Link
      href={opportunity.href}
      className="group rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-ring"
      aria-label={`查看 ${opportunity.match} 的${decisionStateLabels[opportunity.state]}决策`}
    >
      <Card size="sm" className="transition-[box-shadow] group-hover:ring-primary/35">
        <CardContent className="grid grid-cols-2 items-center gap-3 py-4 lg:grid-cols-[minmax(15rem,1.4fr)_minmax(8rem,0.7fr)_minmax(8rem,0.7fr)_minmax(8rem,0.7fr)_auto] md:gap-4">
          <div className="col-span-2 min-w-0 lg:col-span-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="flex min-w-0 items-center gap-1 font-semibold">
                {opportunity.playerNames ? (
                  <>
                    <PlayerName
                      name={opportunity.playerNames[0]}
                      localizedName={opportunity.playerLocalizedNames?.[0]}
                      className="min-w-0 max-w-full"
                      primaryClassName="break-words text-clip overflow-visible whitespace-normal"
                      secondaryClassName="break-words text-clip overflow-visible whitespace-normal"
                    />
                    <span className="shrink-0 text-xs text-muted-foreground">vs.</span>
                    <PlayerName
                      name={opportunity.playerNames[1]}
                      localizedName={opportunity.playerLocalizedNames?.[1]}
                      className="min-w-0 max-w-full"
                      primaryClassName="break-words text-clip overflow-visible whitespace-normal"
                      secondaryClassName="break-words text-clip overflow-visible whitespace-normal"
                    />
                  </>
                ) : opportunity.match}
              </h3>
              <Badge variant="outline">{opportunity.phase === 'live' ? '直播' : '即将开始'}</Badge>
            </div>
            <p className="mt-1 truncate text-sm text-muted-foreground">{opportunity.tournament}</p>
            <div className="mt-2 flex min-w-0 flex-wrap items-center gap-2 text-xs font-medium text-primary">
              <PlayerAvatar name={opportunity.selection} imageUrl={opportunity.selectionImageUrl} className="size-7" />
              <span>方向：</span>
              <PlayerName
                name={opportunity.selection}
                localizedName={opportunity.selectionLocalizedName}
                className="min-w-0 max-w-full"
                primaryClassName="break-words text-clip overflow-visible whitespace-normal"
                secondaryClassName="break-words text-clip overflow-visible whitespace-normal"
              />
              <DecisionStatusBadge state={opportunity.state} overlay={overlay} className="lg:ml-auto" />
            </div>
          </div>

          <dl>
            <dt className="text-xs text-muted-foreground">模型估算胜率</dt>
            <dd className="mt-1 font-mono text-xl font-semibold tabular-nums">{formatPercent(opportunity.modelProbability)}</dd>
          </dl>
          <dl>
            <dt className="text-xs text-muted-foreground">$10 模拟买入均价</dt>
            <dd className="mt-1 font-mono text-xl font-semibold tabular-nums">{formatPercent(opportunity.executableProbability)}</dd>
          </dl>
          <dl>
            <dt className="text-xs text-muted-foreground">模型与市场差距</dt>
            <dd className="mt-1 font-mono text-xl font-semibold text-primary tabular-nums">
              {opportunity.edgePp === null ? '—' : `+${opportunity.edgePp.toFixed(1)} 个百分点`}
            </dd>
            {opportunity.state === 'wait' && opportunity.maxBuyPrice !== null ? (
              <dd className="mt-1 text-xs text-muted-foreground">最高买入价 {formatPercent(opportunity.maxBuyPrice)}</dd>
            ) : null}
          </dl>

          <div className="flex items-center justify-end gap-2 text-xs text-muted-foreground">
            <span>{opportunity.freshness}</span>
            <ArrowRight aria-hidden="true" className="size-4 text-foreground transition-transform group-hover:translate-x-0.5" />
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}
