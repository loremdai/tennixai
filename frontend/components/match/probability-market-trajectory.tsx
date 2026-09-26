'use client'

import { Activity, CircleDashed, Minus, TrendingUp } from 'lucide-react'
import {
  Area,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  XAxis,
  YAxis,
} from 'recharts'

import type { AnalysisState, DecisionPreview } from '@/components/p3/p3-preview-data'
import { PlayerName } from '@/components/player-name'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import { cn } from '@/lib/utils'
import { previewPlayers } from './match-preview-data'

const chartConfig = {
  model: { label: '模型估算胜率', color: 'var(--primary)' },
  market: { label: '10 美元模拟买入价', color: 'var(--chart-2)' },
  uncertainty: { label: '模型估算范围', color: 'var(--primary)' },
} satisfies ChartConfig

function percent(value: number | null): string {
  return value === null ? '暂缺' : `${(value * 100).toFixed(1)}%`
}

export function ProbabilityMarketTrajectory({
  decision,
  analysisState,
}: {
  decision: DecisionPreview
  analysisState: AnalysisState
}) {
  if (analysisState === 'collapsed') {
    return (
      <Card>
        <CardContent className="flex min-h-28 items-center gap-3">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-secondary text-primary">
            <Activity aria-hidden="true" className="size-4" />
          </div>
          <div>
            <h2 className="font-semibold">走势已隐藏</h2>
            <p className="mt-1 text-sm text-muted-foreground">可在页面上方重新显示。</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <section aria-labelledby="probability-market-title">
      <Card>
        <CardHeader className="border-b">
          <div className="flex flex-wrap items-center gap-2">
            <TrendingUp aria-hidden="true" className="size-4 text-primary" />
            <CardTitle><h2 id="probability-market-title">胜率与市场价格走势</h2></CardTitle>
          </div>
          <p className="text-sm text-muted-foreground">对比模型估算胜率与模拟买入价的变化。</p>
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline"><span className="h-0.5 w-5 bg-primary" aria-hidden="true" />模型估算</Badge>
            <Badge variant="outline"><span className="w-5 border-t-2 border-dashed border-chart-2" aria-hidden="true" />市场价格</Badge>
            {decision.overlay === 'gap' ? <Badge variant="destructive"><CircleDashed data-icon="inline-start" aria-hidden="true" />比赛数据更新中断</Badge> : null}
          </div>
        </CardHeader>

        <CardContent className="flex flex-col gap-5">
          <div className="grid grid-cols-2 gap-2" aria-label="球员胜率与价格">
            <div className={cn('rounded-lg border p-3', decision.selection === 'sinner' ? 'border-primary/35 bg-primary/8' : 'bg-muted/20')}>
              <div className="flex items-center justify-between gap-2">
                <PlayerName
                  name={previewPlayers[0].name}
                  localizedName={previewPlayers[0].nameZh}
                  primaryClassName="text-sm font-semibold"
                />
                {decision.selection === 'sinner' ? <Badge variant="secondary">当前选择</Badge> : null}
              </div>
              <p className="mt-2 font-mono text-lg font-semibold">胜率 64.0% <span className="text-muted-foreground">/</span> 买入价 50.4%</p>
            </div>
            <div className={cn('rounded-lg border p-3', decision.selection === 'alcaraz' ? 'border-primary/35 bg-primary/8' : 'bg-muted/20')}>
              <div className="flex items-center justify-between gap-2">
                <PlayerName
                  name={previewPlayers[1].name}
                  localizedName={previewPlayers[1].nameZh}
                  primaryClassName="text-sm font-semibold"
                />
                {decision.selection === 'alcaraz' ? <Badge variant="secondary">当前选择</Badge> : null}
              </div>
              <p className="mt-2 font-mono text-lg font-semibold">胜率 36.0% <span className="text-muted-foreground">/</span> 买入价 50.8%</p>
            </div>
          </div>

          <div className="relative">
            <ChartContainer config={chartConfig} className="h-64 w-full min-w-0">
              <AreaChartContent decision={decision} />
            </ChartContainer>
            {decision.overlay === 'stale' ? (
              <div className="pointer-events-none absolute right-3 top-3 rounded-md border border-destructive/25 bg-background/90 px-2 py-1 text-xs font-medium text-destructive">
                报价更新较慢
              </div>
            ) : null}
          </div>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1.5"><span className="size-2 rounded-full bg-primary" aria-hidden="true" />模型点</span>
            <span className="inline-flex items-center gap-1.5"><span className="size-2 rotate-45 bg-chart-2" aria-hidden="true" />可执行报价点</span>
            <span className="inline-flex items-center gap-1.5"><Minus aria-hidden="true" className="size-3" />买入价与卖出价分别计算</span>
          </div>

          <table className="sr-only">
            <caption>模型估算胜率与 10 美元模拟买入价格变化</caption>
            <thead><tr><th scope="col">时间</th><th scope="col">模型概率</th><th scope="col">市场概率</th></tr></thead>
            <tbody>
              {decision.trajectory.map((point) => (
                <tr key={point.time}>
                  <th scope="row">{point.time}</th>
                  <td>{percent(point.model)}</td>
                  <td>{percent(point.market)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </section>
  )
}

function AreaChartContent({ decision }: { decision: DecisionPreview }) {
  return (
    <LineChart accessibilityLayer data={decision.trajectory} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
      <CartesianGrid vertical={false} strokeDasharray="3 3" />
      <XAxis dataKey="time" tickLine={false} axisLine={false} tickMargin={10} minTickGap={20} />
      <YAxis
        domain={[0.3, 0.75]}
        tickLine={false}
        axisLine={false}
        width={42}
        tickFormatter={(value: number) => `${Math.round(value * 100)}%`}
      />
      <ChartTooltip
        cursor={{ stroke: 'var(--border)', strokeDasharray: '3 3' }}
        content={<ChartTooltipContent formatter={(value) => typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '暂缺'} />}
      />
      <Area
        type="monotone"
        dataKey="uncertainty"
        data={decision.trajectory}
        stroke="none"
        fill="var(--color-uncertainty)"
        fillOpacity={0.1}
        connectNulls={false}
        isAnimationActive={false}
      />
      {decision.overlay === 'stale' ? (
        <ReferenceArea x1="09:42" x2="09:48" fill="var(--muted)" fillOpacity={0.7} strokeOpacity={0} />
      ) : null}
      <Line
        type="monotone"
        dataKey="model"
        data={decision.trajectory}
        stroke="var(--color-model)"
        strokeWidth={2.5}
        dot={{ r: 3, fill: 'var(--background)', strokeWidth: 2 }}
        activeDot={{ r: 5 }}
        connectNulls={false}
        isAnimationActive={false}
      />
      <Line
        type="linear"
        dataKey="market"
        data={decision.trajectory}
        stroke="var(--color-market)"
        strokeWidth={2}
        strokeDasharray="6 5"
        dot={{ r: 3, fill: 'var(--color-market)', strokeWidth: 0 }}
        activeDot={{ r: 5 }}
        connectNulls={false}
        isAnimationActive={false}
      />
    </LineChart>
  )
}
