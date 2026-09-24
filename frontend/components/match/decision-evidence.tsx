import {
  AlertTriangle,
  Ban,
  Check,
  ChevronDown,
  CircleHelp,
  Database,
  ShieldCheck,
} from 'lucide-react'

import type { DecisionPreview, MethodologyState } from '@/components/p3/p3-preview-data'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { cn } from '@/lib/utils'

const gateIcon = {
  pass: Check,
  fail: Ban,
  unknown: CircleHelp,
}

const gateClass = {
  pass: 'border-primary/25 bg-primary/8 text-primary',
  fail: 'border-destructive/25 bg-destructive/8 text-destructive',
  unknown: 'border-border bg-muted/35 text-muted-foreground',
}

export function DecisionEvidence({
  decision,
  methodologyState,
}: {
  decision: DecisionPreview
  methodologyState: MethodologyState
}) {
  return (
    <section aria-labelledby="decision-evidence-title">
      <Card>
        <CardHeader className="border-b">
          <div className="flex items-center gap-2">
            <ShieldCheck aria-hidden="true" className="size-4 text-primary" />
            <CardTitle><h2 id="decision-evidence-title">判断依据</h2></CardTitle>
          </div>
          <p className="text-sm text-muted-foreground">看看哪些比赛和市场信息影响了当前判断。</p>
        </CardHeader>

        <CardContent className="flex flex-col gap-5">
          {decision.confidence === 'empty' || decision.confidence === 'error' ? (
            <div role={decision.confidence === 'error' ? 'alert' : 'status'} className="flex items-start gap-2 rounded-lg border border-destructive/25 bg-destructive/8 p-3 text-sm text-destructive">
              <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              {decision.confidence === 'error'
                ? '暂时无法计算模型估算，已保留其他比赛和市场信息。'
                : '目前可用的数据还不够，暂时无法给出稳定的估算。'}
            </div>
          ) : null}

          <div>
            <h3 className="text-sm font-semibold">影响本次判断的因素</h3>
            <ul className="mt-3 flex flex-col gap-2">
              {decision.reasons.map((reason) => (
                <li key={reason} className="flex items-start gap-2 text-sm leading-relaxed text-muted-foreground">
                  <span className="mt-2 size-1.5 shrink-0 rounded-full bg-primary" aria-hidden="true" />
                  {reason}
                </li>
              ))}
            </ul>
          </div>

          <details open={methodologyState === 'open'} className="group rounded-lg border bg-muted/15">
            <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-semibold outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring">
              <span className="flex items-center gap-2"><Database aria-hidden="true" className="size-4 text-primary" />查看判断细节</span>
              <ChevronDown aria-hidden="true" className="size-4 transition-transform group-open:rotate-180" />
            </summary>
            <div className="flex flex-col gap-5 border-t px-4 py-4 text-sm leading-relaxed text-muted-foreground">
              <div className="grid gap-3 sm:grid-cols-2">
                {decision.gates.map((gate) => {
                  const Icon = gateIcon[gate.status]
                  return (
                    <div key={gate.label} className={cn('flex min-h-20 items-start gap-3 rounded-lg border p-3', gateClass[gate.status])}>
                      <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-background/65"><Icon aria-hidden="true" className="size-4" /></span>
                      <div><p className="text-sm font-semibold">{gate.label}</p><p className="mt-1 text-xs leading-relaxed opacity-85">{gate.detail}</p></div>
                    </div>
                  )
                })}
              </div>
              <p>模型胜率由比赛数据估算；市场价格按实际买卖报价和可交易金额计算，买入价与卖出价分别展示。</p>
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">按 10 美元模拟金额计算</Badge>
                <Badge variant="outline">已计入交易成本</Badge>
                <Badge variant="outline">比赛数据中断时暂停判断</Badge>
                <Badge variant="outline">报价更新较慢时暂停模拟操作</Badge>
              </div>
              <dl className="grid gap-3 rounded-lg bg-muted/30 p-4 text-sm sm:grid-cols-2">
                <div><dt className="text-xs text-muted-foreground">本次判断时间</dt><dd className="mt-1 font-mono text-xs font-semibold">{decision.asOf}</dd></div>
              </dl>
            </div>
          </details>
        </CardContent>
      </Card>
    </section>
  )
}
