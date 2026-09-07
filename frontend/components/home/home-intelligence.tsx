import {
  BarChart3,
  BrainCircuit,
  LockKeyhole,
  ShieldCheck,
} from 'lucide-react'

import type { ProductPhase } from '@/components/match/match-data'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardAction,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

function SignalRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-t py-3 first:border-t-0 first:pt-0 last:pb-0">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="font-mono text-sm font-semibold">{value}</span>
    </div>
  )
}

export function MarketIntelligenceCard({ phase }: { phase: ProductPhase }) {
  const previewEnabled = phase === 'p3'

  return (
    <Card id="markets" data-tone="market" className="scroll-mt-24">
      <CardHeader>
        <div className="flex items-center gap-2">
          <BarChart3 aria-hidden="true" className="size-4 text-primary" />
          <CardTitle>
            <h2>Market Intelligence</h2>
          </CardTitle>
        </div>
        <p className="text-sm text-muted-foreground">AI 驱动的 Polymarket 市场分析</p>
        <CardAction className="flex gap-1.5">
          <Badge data-tone="beta" variant="outline">BETA</Badge>
          <Badge variant="secondary">COMING SOON</Badge>
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <div className="relative overflow-hidden rounded-xl border bg-muted/20 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs text-muted-foreground">Sinner 胜率</p>
              <p className="mt-2 font-mono text-3xl font-semibold text-primary">
                {previewEnabled ? '54%' : '—'}
              </p>
            </div>
            <div className="flex size-9 items-center justify-center rounded-lg bg-secondary text-primary">
              {previewEnabled ? <BrainCircuit aria-hidden="true" className="size-4" /> : <LockKeyhole aria-hidden="true" className="size-4" />}
            </div>
          </div>
          <div className="mt-4 flex h-10 items-end gap-1" aria-hidden="true">
            {[24, 38, 30, 48, 42, 64, 52, 72, 60, 82].map((height, index) => (
              <span
                key={`${height}-${index}`}
                className="flex-1 rounded-t-sm bg-primary/20 last:bg-primary"
                style={{ height: previewEnabled ? `${height}%` : `${Math.max(18, height - 20)}%` }}
              />
            ))}
          </div>
        </div>

        {previewEnabled ? (
          <div>
            <SignalRow label="市场隐含概率" value="51%" />
            <SignalRow label="模型优势" value="+3.0pp" />
            <SignalRow label="置信度" value="72%" />
          </div>
        ) : (
          <p className="text-sm leading-relaxed text-muted-foreground">
            P3 将在同一比赛上下文中加入模型概率、公允价与价值差异；不会改变当前日常比赛信息流。
          </p>
        )}
      </CardContent>

      <CardFooter className="items-start gap-3 text-xs leading-relaxed text-muted-foreground">
        <ShieldCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-primary" />
        概率信息仅用于研究，不构成财务建议。
      </CardFooter>
    </Card>
  )
}
