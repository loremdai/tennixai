import type { PlayerSeasonSummaryPreview } from '@/components/players/player-preview-data'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

function valueOrUnavailable(value: number | null, suffix = '') {
  return value === null ? '暂无' : `${value}${suffix}`
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-muted/55 p-3">
      <p className="text-xs leading-relaxed text-muted-foreground">{label}</p>
      <p className="mt-1.5 font-mono text-lg font-semibold tabular-nums">{value}</p>
    </div>
  )
}

export function PlayerSeasonSummary({ summary }: { summary: PlayerSeasonSummaryPreview }) {
  const hasData = summary.matches !== null
  return (
    <Card aria-labelledby="season-summary-title">
      <CardHeader>
        <div>
          <CardTitle><h2 id="season-summary-title">赛季摘要</h2></CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">与历史赛果年份筛选同步</p>
        </div>
        <CardAction><Badge variant="outline">{summary.season}</Badge></CardAction>
      </CardHeader>
      <CardContent className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="比赛场次" value={valueOrUnavailable(summary.matches)} />
        <Metric
          label="胜–负"
          value={summary.wins === null || summary.losses === null ? '暂无' : `${summary.wins}–${summary.losses}`}
        />
        <Metric label="胜率" value={valueOrUnavailable(summary.winRate, '%')} />
        <Metric label="冠军数" value={valueOrUnavailable(summary.titles)} />
        <Metric label="硬地胜率" value={valueOrUnavailable(summary.hardWinRate, '%')} />
        <Metric label="红土胜率" value={valueOrUnavailable(summary.clayWinRate, '%')} />
        <Metric label="草地胜率" value={valueOrUnavailable(summary.grassWinRate, '%')} />
        <div className="flex items-center rounded-xl bg-secondary/55 p-3 text-xs leading-relaxed text-muted-foreground">
          {hasData ? '仅统计单打正式比赛' : '该赛季统计暂不可用'}
        </div>
      </CardContent>
    </Card>
  )
}
