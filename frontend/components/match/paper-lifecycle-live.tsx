import { BookOpenCheck, Check, CircleOff, Clock3, Dot } from 'lucide-react'

import { DecisionStatusBadge } from '@/components/p3/decision-status'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { PaperModel } from '@/lib/p3-workbench-models'
import { cn } from '@/lib/utils'

function money(value: number | null): string {
  if (value === null) return '—'
  return `${value > 0 ? '+' : value < 0 ? '-' : ''}$${Math.abs(value).toFixed(2)}`
}

const eventIcon = {
  complete: Check,
  pending: Clock3,
  missed: CircleOff,
  neutral: Dot,
}

const eventClass: Record<'complete' | 'pending' | 'missed' | 'neutral', string> = {
  complete: 'border-primary/25 bg-primary/10 text-primary',
  pending: 'border-chart-3/30 bg-chart-3/12 text-chart-3',
  missed: 'border-destructive/25 bg-destructive/10 text-destructive',
  neutral: 'border-border bg-muted text-muted-foreground',
}

/** Production Paper lifecycle (T69): the timeline is ledger-derived; the
 * frontend only maps server event kinds to labels and never reconstructs
 * state from the browser. */
export function PaperLifecycleLive({ paper }: { paper: PaperModel }) {
  const noPosition = paper.state === 'entry_pending' || paper.state === 'missed'

  return (
    <section aria-labelledby="paper-lifecycle-title">
      <Card data-tone="market">
        <CardHeader className="border-b">
          <div className="flex flex-wrap items-center gap-2">
            <BookOpenCheck aria-hidden="true" className="size-4 text-primary" />
            <CardTitle><h2 id="paper-lifecycle-title">Paper lifecycle</h2></CardTitle>
            <DecisionStatusBadge state={paper.state} />
          </div>
          <p className="text-sm text-muted-foreground">intent 一旦出现，missed、exit 与 settled 后仍永久保留完整时间线。</p>
        </CardHeader>

        <CardContent className="flex flex-col gap-5">
          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border bg-border sm:grid-cols-5">
            <dl className="bg-card p-3"><dt className="text-xs text-muted-foreground">入场成本 / 均价</dt><dd className="mt-1 font-mono text-lg font-semibold">{`$${paper.entryCost.toFixed(2)}`} · {paper.averageEntry === null ? '—' : `${(paper.averageEntry * 100).toFixed(1)}%`}</dd></dl>
            <dl className="bg-card p-3"><dt className="text-xs text-muted-foreground">份额</dt><dd className="mt-1 font-mono text-lg font-semibold">{noPosition ? '—' : paper.shares.toFixed(2)}</dd></dl>
            <dl className="bg-card p-3"><dt className="text-xs text-muted-foreground">当前 / 最终价值</dt><dd className="mt-1 font-mono text-lg font-semibold">{noPosition || paper.currentExitValue === null ? '—' : `$${paper.currentExitValue.toFixed(2)}`}</dd></dl>
            <dl className="col-span-2 bg-card p-3 sm:col-span-1">
              <dt className="text-xs text-muted-foreground">净 P&amp;L</dt>
              <dd className={cn(
                'mt-1 font-mono text-lg font-semibold',
                !noPosition && paper.netPnl !== null && paper.netPnl > 0 && 'text-primary',
                !noPosition && paper.netPnl !== null && paper.netPnl < 0 && 'text-destructive',
                noPosition || paper.netPnl === null ? 'text-muted-foreground' : '',
              )}>{noPosition ? '—' : money(paper.netPnl)}</dd>
            </dl>
          </div>

          <ol className="relative flex flex-col" aria-label="Paper 生命周期事件">
            {paper.events.map((item, index) => {
              const Icon = eventIcon[item.status]
              return (
                <li key={item.id} className="grid grid-cols-[2.25rem_minmax(0,1fr)] gap-3 pb-5 last:pb-0">
                  <div className="relative flex justify-center">
                    {index < paper.events.length - 1 ? <span className="absolute bottom-0 top-8 w-px bg-border" aria-hidden="true" /> : null}
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
