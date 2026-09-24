import { Activity, CircleDashed, Minus, TrendingUp } from 'lucide-react'
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from 'recharts'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import type { DecisionOverlay } from '@/components/p3/p3-preview-data'
import type { ChartSideModel, TrajectoryPointModel } from '@/lib/p3-workbench-models'
import { cn } from '@/lib/utils'

const chartConfig = {
  model: { label: '模型估算胜率', color: 'var(--primary)' },
  market: { label: '10 美元模拟买入价', color: 'var(--chart-2)' },
} satisfies ChartConfig

function percent(value: number | null): string {
  return value === null ? '—' : `${(value * 100).toFixed(1)}%`
}

/** Production probability–market chart (T69): both sides keep independent
 * executable asks (never a forced 100% complement), session trajectory
 * samples render gaps instead of interpolated lines, and the chart carries
 * a textual summary plus accessible series names. */
export function ProbabilityMarketChart({
  sides,
  trajectory,
  overlay,
}: {
  sides: ChartSideModel[]
  trajectory: TrajectoryPointModel[]
  overlay: DecisionOverlay
}) {
  const selected = sides.find((side) => side.selected) ?? null
  const summary = selected
    ? `你关注的球员是 ${selected.name}：模型估算胜率为 ${percent(selected.modelProbability)}，10 美元模拟买入价为 ${percent(selected.ask)}。`
    : '选择一位球员，查看模型估算和市场价格。'

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
            {overlay === 'gap' ? <Badge variant="destructive"><CircleDashed data-icon="inline-start" aria-hidden="true" />比赛数据暂时中断</Badge> : null}
            {overlay === 'stale' ? <Badge variant="destructive"><CircleDashed data-icon="inline-start" aria-hidden="true" />报价更新较慢</Badge> : null}
          </div>
        </CardHeader>

        <CardContent className="flex flex-col gap-5">
          <div className="grid grid-cols-2 gap-2" aria-label="球员胜率与价格">
            {sides.map((side) => (
              <div
                key={side.playerId}
                className={cn('rounded-lg border p-3', side.selected ? 'border-primary/35 bg-primary/8' : 'bg-muted/20')}
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate text-sm font-semibold">{side.name}</p>
                  {side.selected ? <Badge variant="secondary">当前选择</Badge> : null}
                </div>
                <p className="mt-2 font-mono text-lg font-semibold">胜率 {percent(side.modelProbability)} <span className="text-muted-foreground">/</span> 买入价 {percent(side.ask)}</p>
              </div>
            ))}
            {sides.length === 0 ? (
              <p className="col-span-2 rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
                暂无可用市场报价。
              </p>
            ) : null}
          </div>

          <p role="note" className="text-sm leading-relaxed text-muted-foreground">{summary}</p>

          {trajectory.length === 0 ? (
            <div className="flex min-h-28 items-center gap-3 rounded-lg border border-dashed bg-muted/15 p-4">
              <Activity aria-hidden="true" className="size-4 shrink-0 text-primary" />
              <p className="text-sm text-muted-foreground">
                暂无走势记录；本次打开页面后才开始记录。
              </p>
            </div>
          ) : (
            <ChartContainer config={chartConfig} className="h-64 w-full min-w-0">
              <LineChart accessibilityLayer data={trajectory} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
                <CartesianGrid vertical={false} strokeDasharray="3 3" />
                <XAxis dataKey="time" tickLine={false} axisLine={false} tickMargin={10} minTickGap={20} />
                <YAxis
                  domain={[0, 1]}
                  tickLine={false}
                  axisLine={false}
                  width={42}
                  tickFormatter={(value: number) => `${Math.round(value * 100)}%`}
                />
                <ChartTooltip
                  cursor={{ stroke: 'var(--border)', strokeDasharray: '3 3' }}
                  content={<ChartTooltipContent formatter={(value) => typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '暂无数据'} />}
                />
                <Line
                  type="monotone"
                  name="模型估算胜率"
                  dataKey="model"
                  stroke="var(--color-model)"
                  strokeWidth={2.5}
                  dot={{ r: 3, fill: 'var(--background)', strokeWidth: 2 }}
                  activeDot={{ r: 5 }}
                  connectNulls={false}
                  isAnimationActive={false}
                />
                <Line
                  type="linear"
                  name="10 美元模拟买入价"
                  dataKey="market"
                  stroke="var(--color-market)"
                  strokeWidth={2}
                  strokeDasharray="6 5"
                  dot={{ r: 3, fill: 'var(--color-market)', strokeWidth: 0 }}
                  activeDot={{ r: 5 }}
                  connectNulls={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ChartContainer>
          )}

          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1.5"><span className="size-2 rounded-full bg-primary" aria-hidden="true" />胜率估算</span>
            <span className="inline-flex items-center gap-1.5"><span className="size-2 rotate-45 bg-chart-2" aria-hidden="true" />模拟买入价</span>
            <span className="inline-flex items-center gap-1.5"><Minus aria-hidden="true" className="size-3" />买入价与卖出价分别显示</span>
          </div>

          <table className="sr-only">
            <caption>本次打开页面后的胜率与模拟买入价记录</caption>
            <thead><tr><th scope="col">时间</th><th scope="col">模型估算胜率</th><th scope="col">模拟买入价</th></tr></thead>
            <tbody>
              {trajectory.map((point, index) => (
                <tr key={`${point.time}-${index}`}>
                  <th scope="row">{point.time}</th>
                <td>{point.model === null ? '暂无数据' : percent(point.model)}</td>
                  <td>{point.market === null ? '暂无数据' : percent(point.market)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </section>
  )
}
