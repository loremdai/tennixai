import type { PlayerSeasonSummaryPreview, SurfaceRecordPreview } from '@/components/players/player-preview-data'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

function Metric({
  label,
  value,
  source,
}: {
  label: string
  value: string
  source?: string
}) {
  return (
    <div className="rounded-xl bg-muted/55 p-3">
      <p className="text-xs leading-relaxed text-muted-foreground">{label}</p>
      <p className="mt-1.5 font-mono text-lg font-semibold tabular-nums">{value}</p>
      {source ? <p className="mt-1 text-[10px] leading-relaxed text-muted-foreground">{source}</p> : null}
    </div>
  )
}

function hasCompleteSurfaceRecord(
  record: SurfaceRecordPreview | null,
): record is { won: number; lost: number } {
  return record !== null
    && record.won !== null
    && record.lost !== null
}

export function hasSeasonSummaryMetrics(summary: PlayerSeasonSummaryPreview) {
  return summary.matches !== null
    || (summary.wins !== null && summary.losses !== null)
    || summary.winRate !== null
    || summary.titles !== null
    || hasCompleteSurfaceRecord(summary.hard)
    || hasCompleteSurfaceRecord(summary.clay)
    || hasCompleteSurfaceRecord(summary.grass)
}

export function PlayerSeasonSummary({ summary }: { summary: PlayerSeasonSummaryPreview }) {
  if (!hasSeasonSummaryMetrics(summary)) return null

  const recordedResultSource = summary.resultBasis === 'recorded_results'
    ? '按收录单打赛果计算'
    : undefined
  const metrics: { label: string; value: string; source?: string }[] = []
  if (summary.matches !== null) {
    metrics.push({ label: '比赛场次', value: String(summary.matches), source: recordedResultSource })
  }
  if (summary.wins !== null && summary.losses !== null) {
    metrics.push({ label: '胜–负', value: `${summary.wins}–${summary.losses}`, source: recordedResultSource })
  }
  if (summary.winRate !== null) {
    metrics.push({ label: '胜率', value: `${summary.winRate}%`, source: recordedResultSource })
  }
  if (summary.titles !== null) {
    metrics.push({ label: '冠军数', value: String(summary.titles) })
  }
  for (const [label, record] of [
    ['硬地胜负', summary.hard],
    ['红土胜负', summary.clay],
    ['草地胜负', summary.grass],
  ] as const) {
    if (hasCompleteSurfaceRecord(record)) {
      metrics.push({ label, value: `${record.won}–${record.lost}` })
    }
  }

  return (
    <Card aria-labelledby="season-summary-title">
      <CardHeader>
        <div>
          <CardTitle><h2 id="season-summary-title">赛季摘要</h2></CardTitle>
        </div>
        <CardAction><Badge variant="outline">{summary.season}</Badge></CardAction>
      </CardHeader>
      <CardContent className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {metrics.map((metric) => <Metric key={metric.label} {...metric} />)}
      </CardContent>
    </Card>
  )
}
