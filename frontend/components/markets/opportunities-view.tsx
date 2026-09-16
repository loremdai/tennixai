import Link from 'next/link'
import { ArrowRight, Radar, ShieldCheck } from 'lucide-react'

import { DecisionStatusBadge } from '@/components/p3/decision-status'
import {
  opportunityFixtures,
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
    freshness: state === 'partial_stale' && index === 1 ? '最后可信 · 2 分 08 秒前' : item.freshness,
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
            <h2 className="font-semibold">暂无符合门槛的机会</h2>
            <p className="mt-1 max-w-md text-sm leading-relaxed text-muted-foreground">
              覆盖市场仍在监测中；下一次通过 hard gate 的 BUY 或 WAIT 会出现在这里。
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
          <h2 id="opportunities-title" className="text-lg font-semibold">按决策优先级排序</h2>
          <p className="mt-1 text-sm text-muted-foreground">直播 BUY 优先，其次是即将开始的价格等待。</p>
        </div>
        <span className="font-mono text-xs text-muted-foreground">{opportunities.length} 条</span>
      </div>

      <div className="grid gap-3">
        {opportunities.map((opportunity) => (
          <Link
            key={opportunity.id}
            href={opportunity.href}
            className="group rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label={`查看 ${opportunity.match} 的 ${opportunity.state} 决策`}
          >
            <Card size="sm" className="transition-[transform,box-shadow] group-hover:-translate-y-0.5 group-hover:ring-primary/35">
              <CardContent className="grid min-h-28 grid-cols-2 items-center gap-4 py-1 md:grid-cols-[minmax(15rem,1.5fr)_minmax(8rem,0.7fr)_minmax(8rem,0.7fr)_minmax(8rem,0.7fr)_auto_auto]">
                <div className="col-span-2 min-w-0 md:col-span-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="truncate font-semibold">{opportunity.match}</h3>
                    <Badge variant="outline">{opportunity.phase === 'live' ? '直播' : '即将开始'}</Badge>
                  </div>
                  <p className="mt-1 truncate text-sm text-muted-foreground">{opportunity.tournament}</p>
                  <p className="mt-2 text-xs font-medium text-primary">方向：{opportunity.selection}</p>
                </div>

                <dl>
                  <dt className="text-xs text-muted-foreground">模型概率</dt>
                  <dd className="mt-1 font-mono text-xl font-semibold tabular-nums">{formatPercent(opportunity.modelProbability)}</dd>
                </dl>
                <dl>
                  <dt className="text-xs text-muted-foreground">$10 可执行均价</dt>
                  <dd className="mt-1 font-mono text-xl font-semibold tabular-nums">{formatPercent(opportunity.executableProbability)}</dd>
                </dl>
                <dl>
                  <dt className="text-xs text-muted-foreground">保守净 edge</dt>
                  <dd className="mt-1 font-mono text-xl font-semibold text-primary tabular-nums">+{opportunity.edgePp.toFixed(1)}pp</dd>
                  {opportunity.maxBuyPrice !== null ? (
                    <dd className="mt-1 text-xs text-muted-foreground">最高价 {formatPercent(opportunity.maxBuyPrice)}</dd>
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
        ))}
      </div>

      <div className="flex items-start gap-2 rounded-lg bg-muted/25 p-3 text-xs leading-relaxed text-muted-foreground">
        <ShieldCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-primary" />
        BUY 与 WAIT 是研究状态；整行只进入比赛证据页，不执行真实交易。
      </div>
    </section>
  )
}
