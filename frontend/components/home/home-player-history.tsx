import { MatchResultCard } from '@/components/home/home-match-result-card'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import type { PlayerSeasonRecordDto, StructuredData } from '@/lib/api/types'
import type { HomeMatchViewModel } from '@/lib/view-models'
import { toHomeMatch } from '@/lib/view-models'
import {
  historyEmptyCopy,
  historyPlayerHeading,
  historyQualityCopy,
  historyScopeLabel,
  seasonSurfaceEntries,
  seasonWinRate,
} from '@/lib/player-history-view'

function SeasonRecordSummary({ record }: { record: PlayerSeasonRecordDto }) {
  const winRate = seasonWinRate(record)
  const surfaces = seasonSurfaceEntries(record)

  return (
    <Card size="sm" className="bg-background/45" data-testid="season-record-summary">
      <CardContent className="flex flex-col gap-4">
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-xs sm:grid-cols-4">
          <div>
            <dt className="text-muted-foreground">胜场</dt>
            <dd className="mt-1 font-mono text-lg font-semibold text-primary tabular-nums">
              {record.matches_won ?? '暂无'}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">负场</dt>
            <dd className="mt-1 font-mono text-lg font-semibold tabular-nums">
              {record.matches_lost ?? '暂无'}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">胜率</dt>
            <dd className="mt-1 font-mono text-lg font-semibold tabular-nums">
              {winRate ?? '—'}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">冠军</dt>
          <dd className="mt-1 font-mono text-lg font-semibold tabular-nums">{record.titles ?? '暂无'}</dd>
          </div>
        </dl>
        {surfaces.length > 0 ? (
          <div className="flex flex-wrap gap-2 text-xs">
            {surfaces.map((surface) => (
              <span
                key={surface.label}
                className="rounded-lg bg-muted/25 px-3 py-1.5"
                data-testid="season-surface-record"
              >
                <span className="text-muted-foreground">{surface.label}</span>
                {' '}
                <span className="font-mono font-medium tabular-nums">{surface.text}</span>
              </span>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

export function HomePlayerHistory({
  items,
  onFollowUp,
}: {
  items: StructuredData[]
  onFollowUp: (match: HomeMatchViewModel) => void
}) {
  return (
    <>
      {items.map((item, index) => {
        const history = item.player_history
        if (!history) return null
        const heading = historyPlayerHeading(history)
        const scopeLabel = historyScopeLabel(history)
        const qualityCopy = historyQualityCopy(history)
        return (
          <section
            key={`${history.player.id}-${history.scope}-${history.season ?? 'results'}-${index}`}
            className="flex flex-col gap-3"
            aria-label={`${heading} ${scopeLabel}`}
            data-testid="player-history-section"
          >
            <header className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-pretty text-base font-semibold">{heading}</h3>
              <Badge variant="outline">{scopeLabel}</Badge>
            </header>
            {history.scope === 'season' ? (
              history.season_record ? (
                <SeasonRecordSummary record={history.season_record} />
              ) : (
                <p className="text-sm text-muted-foreground">{historyEmptyCopy(history)}</p>
              )
            ) : item.matches.length > 0 ? (
              <div className="flex flex-col gap-3">
                {qualityCopy ? (
                  <p role="note" className="text-xs text-muted-foreground">
                    {qualityCopy}
                  </p>
                ) : null}
                {item.matches.map((match) => (
                  <MatchResultCard
                    key={match.id}
                    match={toHomeMatch(match)}
                    onFollowUp={onFollowUp}
                  />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">{historyEmptyCopy(history)}</p>
            )}
          </section>
        )
      })}
    </>
  )
}
