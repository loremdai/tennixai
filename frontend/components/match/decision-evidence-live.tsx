import {
  AlertTriangle,
  Ban,
  Check,
  ChevronDown,
  CircleHelp,
  Database,
  ShieldCheck,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { EvidenceModel } from '@/lib/p3-workbench-models'
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

/** Production Decision Evidence (T69): structured reasons, versions and
 * hard gates exactly as the server recorded them; no LLM attribution. */
export function DecisionEvidenceLive({ evidence }: { evidence: EvidenceModel }) {
  return (
    <section aria-labelledby="decision-evidence-title">
      <Card>
        <CardHeader className="border-b">
          <div className="flex items-center gap-2">
            <ShieldCheck aria-hidden="true" className="size-4 text-primary" />
            <CardTitle><h2 id="decision-evidence-title">Decision Evidence &amp; Gates</h2></CardTitle>
          </div>
          <p className="text-sm text-muted-foreground">只展示结构化 reasons、版本、hard gates 与降级；不让 LLM 生成归因。</p>
        </CardHeader>

        <CardContent className="flex flex-col gap-5">
          {evidence.availabilityBanner ? (
            <div role="status" className="flex items-start gap-2 rounded-lg border border-destructive/25 bg-destructive/8 p-3 text-sm text-destructive">
              <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              {evidence.availabilityBanner}
            </div>
          ) : null}

          {evidence.gates.length === 0 ? (
            <p className="rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
              本次快照未附带 gate 明细；结构化 reasons 与版本如下。
            </p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {evidence.gates.map((gate, index) => {
                const Icon = gateIcon[gate.status]
                return (
                  <div key={`${gate.label}-${index}`} className={cn('flex min-h-24 items-start gap-3 rounded-lg border p-3', gateClass[gate.status])}>
                    <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-background/65">
                      <Icon aria-hidden="true" className="size-4" />
                    </span>
                    <div>
                      <p className="text-sm font-semibold">{gate.label}</p>
                      <p className="mt-1 text-xs leading-relaxed opacity-85">{gate.detail}</p>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.35fr)_minmax(15rem,0.65fr)]">
            <div>
              <h3 className="text-sm font-semibold">结构化证据</h3>
              <ul className="mt-3 flex flex-col gap-2">
                {evidence.reasons.map((reason) => (
                  <li key={reason} className="flex items-start gap-2 text-sm leading-relaxed text-muted-foreground">
                    <span className="mt-2 size-1.5 shrink-0 rounded-full bg-primary" aria-hidden="true" />
                    {reason}
                  </li>
                ))}
              </ul>
            </div>

            <dl className="flex flex-col gap-3 rounded-lg bg-muted/30 p-4 text-sm">
              <div>
                <dt className="text-xs text-muted-foreground">模型版本</dt>
                <dd className="mt-1 break-all font-mono text-xs font-semibold">{evidence.modelVersion}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">校准版本</dt>
                <dd className="mt-1 break-all font-mono text-xs font-semibold">{evidence.calibrationVersion}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">策略版本</dt>
                <dd className="mt-1 break-all font-mono text-xs font-semibold">{evidence.policyVersion}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">数据版本</dt>
                <dd className="mt-1 break-all font-mono text-xs font-semibold">{evidence.dataVersion}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">可信快照时间</dt>
                <dd className="mt-1 font-mono text-xs font-semibold">{evidence.asOf}</dd>
              </div>
            </dl>
          </div>

          <details className="group rounded-lg border bg-muted/15">
            <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-semibold outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring">
              <span className="flex items-center gap-2"><Database aria-hidden="true" className="size-4 text-primary" />方法与计算口径</span>
              <ChevronDown aria-hidden="true" className="size-4 transition-transform group-open:rotate-180" />
            </summary>
            <div className="border-t px-4 py-4 text-sm leading-relaxed text-muted-foreground">
              <p>
                模型概率来自固定版本的结构化比赛特征。市场概率按目标方向的可执行订单深度计算；两侧 ask 与 bid 永远独立，不把其中一侧写成另一侧的简单补数。
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Badge variant="outline">$10 深度口径</Badge>
                <Badge variant="outline">净 edge 含 spread</Badge>
                <Badge variant="outline">gap 不插值</Badge>
                <Badge variant="outline">freshness 撤销动作</Badge>
              </div>
            </div>
          </details>
        </CardContent>
      </Card>
    </section>
  )
}
