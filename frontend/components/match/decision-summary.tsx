import { AlertTriangle, Clock3, Sparkles } from 'lucide-react'

import { DecisionStatusBadge } from '@/components/p3/decision-status'
import type { DecisionPreview } from '@/components/p3/p3-preview-data'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardAction,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { cn } from '@/lib/utils'

function percent(value: number | null): string {
  return value === null ? '—' : `${(value * 100).toFixed(1)}%`
}

function edge(value: number | null): string {
  return value === null ? '—' : `${value > 0 ? '+' : ''}${value.toFixed(1)} 个百分点`
}

export function DecisionSummary({
  decision,
  onAsk,
}: {
  decision: DecisionPreview
  onAsk: () => void
}) {
  const quoteLabel = decision.quoteSide === 'ask'
    ? '10 美元模拟买入均价'
    : decision.quoteSide === 'bid'
      ? '10 美元模拟卖出均价'
      : '市场参考价格'

  return (
    <section aria-labelledby="decision-summary-title">
      <Card data-tone="market" className="overflow-hidden ring-1 ring-primary/15">
        <CardHeader className="border-b bg-muted/20">
          <div className="flex flex-wrap items-center gap-2">
            <DecisionStatusBadge state={decision.state} overlay={decision.overlay} />
          </div>
          <CardTitle>
            <h2 id="decision-summary-title" className="max-w-3xl text-balance text-xl tracking-tight sm:text-2xl">
              {decision.title}
            </h2>
          </CardTitle>
          <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">{decision.description}</p>
          <CardAction>
            <Button variant="outline" onClick={onAsk}>
              <Sparkles data-icon="inline-start" aria-hidden="true" />
              问这场比赛
            </Button>
          </CardAction>
        </CardHeader>

        <CardContent className="flex flex-col gap-4">
          {decision.overlay !== 'none' ? (
            <div role="status" className="flex items-start gap-2 rounded-lg border border-destructive/25 bg-destructive/8 p-3 text-sm text-destructive">
              <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              <span>
                {decision.overlay === 'stale'
                  ? '市场报价更新较慢，已暂停新的模拟操作。'
                  : '比赛数据更新中断，已暂停新的模拟操作。'}
                最近一次有效数据仍保留；恢复更新后会重新评估。
              </span>
            </div>
          ) : null}

          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border bg-border sm:grid-cols-3 lg:grid-cols-4">
            <dl className="min-h-24 bg-card p-4">
              <dt className="text-xs text-muted-foreground">关注球员</dt>
              <dd className="mt-2 text-sm font-semibold">{decision.selectionLabel}</dd>
            </dl>
            <dl className="min-h-24 bg-card p-4">
              <dt className="text-xs text-muted-foreground">模型估算胜率</dt>
              <dd className="mt-2 font-mono text-2xl font-semibold tabular-nums">{percent(decision.modelProbability)}</dd>
              {decision.modelProbability === null ? <dd className="mt-1 text-xs text-muted-foreground">暂未提供胜率估算，仅显示市场报价</dd> : null}
            </dl>
            <dl className="min-h-24 bg-card p-4">
              <dt className="text-xs text-muted-foreground">{quoteLabel}</dt>
              <dd className="mt-2 font-mono text-2xl font-semibold tabular-nums">{percent(decision.executableProbability)}</dd>
              <dd className="mt-1 text-xs text-muted-foreground">按实时买卖报价估算</dd>
            </dl>
            <dl className="min-h-24 bg-card p-4">
              <dt className="text-xs text-muted-foreground">模型与市场差距</dt>
              <dd className={cn(
                'mt-2 font-mono text-2xl font-semibold tabular-nums',
                decision.edgePp !== null && decision.edgePp > 0 && 'text-primary',
                decision.edgePp !== null && decision.edgePp < 0 && 'text-destructive',
              )}>{edge(decision.edgePp)}</dd>
              {decision.maxBuyPrice !== null ? <dd className="mt-1 text-xs text-muted-foreground">重新评估参考价 {percent(decision.maxBuyPrice)}</dd> : null}
            </dl>
          </div>

          <div className="flex flex-col justify-between gap-3 rounded-lg bg-muted/25 p-3 sm:flex-row sm:items-center">
            <div>
              <p className="text-sm font-medium">{decision.eyebrow}</p>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{decision.reason}</p>
            </div>
            <div className="flex shrink-0 flex-col gap-1 text-xs text-muted-foreground sm:text-right">
              <span className="inline-flex items-center gap-1.5 sm:justify-end"><Clock3 aria-hidden="true" className="size-3.5" />{decision.marketFreshness}</span>
              <span>{decision.modelFreshness}</span>
            </div>
          </div>
        </CardContent>

        <CardFooter className="items-start gap-3 text-xs leading-relaxed text-muted-foreground">
          <span className="mt-0.5 size-2 shrink-0 rounded-full bg-primary" aria-hidden="true" />
          胜率由模型估算，价格来自实时市场。这里仅记录模拟交易，不会真实下单。
        </CardFooter>
      </Card>
    </section>
  )
}
