import { AlertTriangle, ArrowDownToLine, Clock3, Sparkles } from 'lucide-react'

import { DecisionStatusBadge } from '@/components/p3/decision-status'
import type { DecisionPreview } from '@/components/p3/p3-preview-data'
import { Badge } from '@/components/ui/badge'
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
  return value === null ? '—' : `${value > 0 ? '+' : ''}${value.toFixed(1)}pp`
}

function money(value: number | null): string {
  if (value === null) return '—'
  return `${value > 0 ? '+' : value < 0 ? '-' : ''}$${Math.abs(value).toFixed(2)}`
}

export function DecisionSummary({
  decision,
  onAsk,
}: {
  decision: DecisionPreview
  onAsk: () => void
}) {
  const quoteLabel = decision.quoteSide === 'ask'
    ? '$10 可执行 ask'
    : decision.quoteSide === 'bid'
      ? '$10 可执行 bid'
      : '$10 可执行市场概率'

  return (
    <section aria-labelledby="decision-summary-title">
      <Card data-tone="market" className="overflow-hidden ring-1 ring-primary/15">
        <CardHeader className="border-b bg-muted/20">
          <div className="flex flex-wrap items-center gap-2">
            <Badge data-tone="beta" variant="outline">P3 PREVIEW</Badge>
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
                  ? 'STALE：已超过 freshness 阈值。'
                  : 'DATA GAP：轨迹存在不可插值的数据缺口。'}
                最后可信数字与时间保留，但基础 {decision.stateLabel} 动作已撤销。
              </span>
            </div>
          ) : null}

          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border bg-border sm:grid-cols-3 lg:grid-cols-6">
            <dl className="min-h-24 bg-card p-4">
              <dt className="text-xs text-muted-foreground">研究方向</dt>
              <dd className="mt-2 text-sm font-semibold">{decision.selectionLabel}</dd>
            </dl>
            <dl className="min-h-24 bg-card p-4">
              <dt className="text-xs text-muted-foreground">模型概率</dt>
              <dd className="mt-2 font-mono text-2xl font-semibold tabular-nums">{percent(decision.modelProbability)}</dd>
              {decision.modelProbability === null ? <dd className="mt-1 text-xs text-muted-foreground">未覆盖，不伪造</dd> : null}
            </dl>
            <dl className="min-h-24 bg-card p-4">
              <dt className="text-xs text-muted-foreground">{quoteLabel}</dt>
              <dd className="mt-2 font-mono text-2xl font-semibold tabular-nums">{percent(decision.executableProbability)}</dd>
              <dd className="mt-1 text-xs text-muted-foreground">两侧独立报价</dd>
            </dl>
            <dl className="min-h-24 bg-card p-4">
              <dt className="text-xs text-muted-foreground">保守净 edge</dt>
              <dd className={cn(
                'mt-2 font-mono text-2xl font-semibold tabular-nums',
                decision.edgePp !== null && decision.edgePp > 0 && 'text-primary',
                decision.edgePp !== null && decision.edgePp < 0 && 'text-destructive',
              )}>{edge(decision.edgePp)}</dd>
              {decision.maxBuyPrice !== null ? <dd className="mt-1 text-xs text-muted-foreground">最高可买 {percent(decision.maxBuyPrice)}</dd> : null}
            </dl>
            <dl className="min-h-24 bg-card p-4">
              <dt className="text-xs text-muted-foreground">$10 Paper EV</dt>
              <dd className="mt-2 font-mono text-2xl font-semibold text-primary tabular-nums">{money(decision.paperEv)}</dd>
              <dd className="mt-1 text-xs text-muted-foreground">含执行缓冲</dd>
            </dl>
            <dl className="min-h-24 bg-card p-4">
              <dt className="text-xs text-muted-foreground">置信度</dt>
              <dd className="mt-2 font-mono text-2xl font-semibold tabular-nums">{decision.confidenceValue ?? '—'}</dd>
              <dd className="mt-1 text-xs text-muted-foreground">{decision.confidenceLabel}</dd>
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
          <ArrowDownToLine aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-primary" />
          状态由结构化规则、模型版本和 hard gates 产生；LLM 不生成概率、价格或决策归因。仅用于研究与 Paper 模拟。
        </CardFooter>
      </Card>
    </section>
  )
}
