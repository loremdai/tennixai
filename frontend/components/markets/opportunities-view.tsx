import Link from 'next/link'
import { ArrowRight, Radar, ShieldCheck } from 'lucide-react'

import { DecisionStatusBadge, decisionStateLabels } from '@/components/p3/decision-status'
import { PlayerAvatar } from '@/components/player-avatar'
import {
  opportunityFixtures,
  splitPreviewMatchPlayers,
  type MarketsPreviewState,
} from '@/components/p3/p3-preview-data'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

export function OpportunitiesView({ state }: { state: MarketsPreviewState }) {
  const opportunities = state === 'empty' ? [] : opportunityFixtures.map((item, index) => ({
    ...item,
    stale: state === 'partial_stale' && index === 1 ? true : item.stale,
    freshness: state === 'partial_stale' && index === 1 ? '上次有效报价 · 2 分 08 秒前' : item.freshness,
    href: state === 'partial_stale' && index === 1 ? `${item.href}&overlay=stale` : item.href,
  }))

  if (opportunities.length === 0) {
    return (
      <Card>
        <CardContent className="flex min-h-72 flex-col items-center justify-center gap-3 text-center">
          <div className="flex size-10 items-center justify-center rounded-lg bg-secondary text-primary">
            <Radar aria-hidden="true" className="size-5" />
          </div>
          <div>
            <h2 className="font-semibold">暂时没有值得关注的机会</h2>
            <p className="mt-1 max-w-md text-sm leading-relaxed text-muted-foreground">
              目前没有比赛同时满足模型判断和报价条件。你可以先查看所有市场的最新报价。
            </p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <section className="flex flex-col gap-3" aria-labelledby="opportunities-title">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h2 id="opportunities-title" className="text-lg font-semibold">值得关注的比赛</h2>
          <p className="mt-1 text-sm text-muted-foreground">正在进行的比赛优先，其次是即将开始的比赛。</p>
        </div>
        <span className="font-mono text-xs text-muted-foreground">{opportunities.length} 条</span>
      </div>

      <div className="grid gap-3">
        {opportunities.map((opportunity) => {
          const [playerOne, playerTwo] = splitPreviewMatchPlayers(opportunity.match)
          return (
            <Link
              key={opportunity.id}
              href={opportunity.href}
              className="group rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label={`查看 ${opportunity.match} 的${decisionStateLabels[opportunity.state]}判断`}
            >
              <Card size="sm" className="transition-[transform,box-shadow] group-hover:-translate-y-0.5 group-hover:ring-primary/35">
                <CardContent className="grid min-h-28 grid-cols-2 items-center gap-4 py-1 md:grid-cols-[minmax(15rem,1.5fr)_minmax(8rem,0.7fr)_minmax(8rem,0.7fr)_minmax(8rem,0.7fr)_auto_auto]">
                  <div className="col-span-2 min-w-0 md:col-span-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="flex min-w-0 items-center gap-2">
                        <PlayerAvatar name={playerOne} className="size-7" />
                        <h3 className="truncate font-semibold">{opportunity.match}</h3>
                        <PlayerAvatar name={playerTwo} className="size-7" />
                      </div>
                      <Badge variant="outline">{opportunity.phase === 'live' ? '直播' : '即将开始'}</Badge>
                    </div>
                    <p className="mt-1 truncate text-sm text-muted-foreground">{opportunity.tournament}</p>
                    <p className="mt-2 text-xs font-medium text-primary">方向：{opportunity.selection}</p>
                  </div>

                  <dl>
                    <dt className="text-xs text-muted-foreground">模型估算胜率</dt>
                    <dd className="mt-1 font-mono text-xl font-semibold tabular-nums">{formatPercent(opportunity.modelProbability)}</dd>
                  </dl>
                  <dl>
                    <dt className="text-xs text-muted-foreground">10 美元模拟买入价</dt>
                    <dd className="mt-1 font-mono text-xl font-semibold tabular-nums">{formatPercent(opportunity.executableProbability)}</dd>
                  </dl>
                  <dl>
                    <dt className="text-xs text-muted-foreground">模型与市场差距</dt>
                    <dd className="mt-1 font-mono text-xl font-semibold text-primary tabular-nums">+{opportunity.edgePp.toFixed(1)} 个百分点</dd>
                    {opportunity.maxBuyPrice !== null ? (
                      <dd className="mt-1 text-xs text-muted-foreground">参考买入价 {formatPercent(opportunity.maxBuyPrice)}</dd>
                    ) : null}
                  </dl>

                  <DecisionStatusBadge state={opportunity.state} overlay={opportunity.stale ? 'stale' : 'none'} />
                  <div className="flex items-center justify-end gap-2 text-xs text-muted-foreground">
                    <span>{opportunity.freshness}</span>
                    <ArrowRight aria-hidden="true" className="size-4 text-foreground transition-transform group-hover:translate-x-0.5" />
                  </div>
                </CardContent>
              </Card>
            </Link>
          )
        })}
      </div>

      <div className="flex items-start gap-2 rounded-lg bg-muted/25 p-3 text-xs leading-relaxed text-muted-foreground">
        <ShieldCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-primary" />
        这些判断仅供参考；查看比赛详情不会进行真实交易。
      </div>
    </section>
  )
}
