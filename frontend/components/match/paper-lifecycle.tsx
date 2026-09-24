import { BookOpenCheck, Check, CircleOff, Clock3, Dot } from 'lucide-react'

import { DecisionStatusBadge } from '@/components/p3/decision-status'
import type { DecisionPreview, PaperEvent } from '@/components/p3/p3-preview-data'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { cn } from '@/lib/utils'

function money(value: number): string {
  return `${value > 0 ? '+' : value < 0 ? '-' : ''}$${Math.abs(value).toFixed(2)}`
}

const eventIcon = {
  complete: Check,
  pending: Clock3,
  missed: CircleOff,
  neutral: Dot,
}

const eventClass: Record<PaperEvent['status'], string> = {
  complete: 'border-primary/25 bg-primary/10 text-primary',
  pending: 'border-chart-3/30 bg-chart-3/12 text-chart-3',
  missed: 'border-destructive/25 bg-destructive/10 text-destructive',
  neutral: 'border-border bg-muted text-muted-foreground',
}

export function PaperLifecycle({ decision }: { decision: DecisionPreview }) {
  if (!decision.paper) return null
  const noPosition = decision.state === 'entry_pending' || decision.state === 'missed'

  return (
    <section aria-labelledby="paper-lifecycle-title">
      <Card data-tone="market">
        <CardHeader className="border-b">
          <div className="flex flex-wrap items-center gap-2">
            <BookOpenCheck aria-hidden="true" className="size-4 text-primary" />
            <CardTitle><h2 id="paper-lifecycle-title">模拟交易记录</h2></CardTitle>
            <DecisionStatusBadge state={decision.state} />
          </div>
          <p className="text-sm text-muted-foreground">完整记录模拟买入、退出、未成交和结算情况。</p>
        </CardHeader>

        <CardContent className="flex flex-col gap-5">
          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border bg-border sm:grid-cols-5">
            <dl className="bg-card p-3"><dt className="text-xs text-muted-foreground">模拟投入</dt><dd className="mt-1 font-mono text-lg font-semibold">${decision.paper.entryCost.toFixed(2)}</dd></dl>
            <dl className="bg-card p-3"><dt className="text-xs text-muted-foreground">模拟买入均价</dt><dd className="mt-1 font-mono text-lg font-semibold">{(decision.paper.averageEntry * 100).toFixed(1)}%</dd></dl>
            <dl className="bg-card p-3"><dt className="text-xs text-muted-foreground">持有份数</dt><dd className="mt-1 font-mono text-lg font-semibold">{noPosition ? '—' : decision.paper.shares.toFixed(2)}</dd></dl>
            <dl className="bg-card p-3"><dt className="text-xs text-muted-foreground">当前模拟卖出价值</dt><dd className="mt-1 font-mono text-lg font-semibold">{noPosition ? '—' : `$${decision.paper.currentExitValue.toFixed(2)}`}</dd></dl>
            <dl className="col-span-2 bg-card p-3 sm:col-span-1">
              <dt className="text-xs text-muted-foreground">模拟盈亏</dt>
              <dd className={cn(
                'mt-1 font-mono text-lg font-semibold',
                !noPosition && decision.paper.netPnl > 0 && 'text-primary',
                !noPosition && decision.paper.netPnl < 0 && 'text-destructive',
              )}>{noPosition ? '—' : money(decision.paper.netPnl)}</dd>
            </dl>
          </div>

          <ol className="relative flex flex-col" aria-label="模拟交易记录">
            {decision.paper.events.map((item, index) => {
              const Icon = eventIcon[item.status]
              return (
                <li key={item.id} className="grid grid-cols-[2.25rem_minmax(0,1fr)] gap-3 pb-5 last:pb-0">
                  <div className="relative flex justify-center">
                    {index < decision.paper!.events.length - 1 ? <span className="absolute bottom-0 top-8 w-px bg-border" aria-hidden="true" /> : null}
                    <span className={cn('relative z-10 flex size-8 items-center justify-center rounded-full border', eventClass[item.status])}>
                      <Icon aria-hidden="true" className="size-4" />
                    </span>
                  </div>
                  <div className="min-w-0 pt-0.5">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-semibold">{item.title}</p>
                      <time className="font-mono text-xs text-muted-foreground">{item.time}</time>
                    </div>
                    <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{item.detail}</p>
                  </div>
                </li>
              )
            })}
          </ol>
        </CardContent>
      </Card>
    </section>
  )
}
