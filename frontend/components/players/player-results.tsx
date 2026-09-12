'use client'

import { Fragment, useMemo, useState } from 'react'
import Link from 'next/link'
import {
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock3,
  DatabaseZap,
  RotateCcw,
} from 'lucide-react'

import { PlayerCountry } from '@/components/player-country'
import type {
  CompetitionTier,
  MatchOutcome,
  PlayerHistoryState,
  PlayerResultPreview,
  TourKey,
} from '@/components/players/player-preview-data'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardAction,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

const seasonOptions = [2026, 2025, 2024, 2023, 2022]
const tierOptions: Array<{ value: 'ALL' | CompetitionTier; label: string }> = [
  { value: 'ALL', label: '全部级别' },
  { value: 'ATP', label: 'ATP' },
  { value: 'WTA', label: 'WTA' },
  { value: 'Challenger', label: 'Challenger' },
  { value: 'ITF', label: 'ITF' },
  { value: 'Other', label: 'Other' },
]
const outcomeOptions: Array<{ value: 'ALL' | MatchOutcome; label: string }> = [
  { value: 'ALL', label: '全部结果' },
  { value: 'win', label: '胜' },
  { value: 'loss', label: '负' },
]

function FilterMenu<T extends string | number>({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: T
  options: Array<{ value: T; label: string }>
  onChange: (value: T) => void
}) {
  const selected = options.find((option) => option.value === value)?.label
  return (
    <DropdownMenu>
      <DropdownMenuTrigger render={<Button variant="outline" size="lg" aria-label={`${label}：${selected}`} />}>
        <span className="text-muted-foreground">{label}</span>
        {selected}
        <ChevronDown data-icon="inline-end" aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-44">
        <DropdownMenuGroup>
          <DropdownMenuLabel>{label}</DropdownMenuLabel>
          {options.map((option) => (
            <DropdownMenuItem key={String(option.value)} onClick={() => onChange(option.value)}>
              <span className="flex size-4 items-center justify-center">
                {option.value === value ? <Check aria-hidden="true" /> : null}
              </span>
              {option.label}
            </DropdownMenuItem>
          ))}
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function LoadingResults() {
  return (
    <div className="flex flex-col" aria-label="正在加载历史赛果" aria-busy="true">
      <span className="sr-only">正在加载历史赛果</span>
      {Array.from({ length: 6 }, (_, index) => (
        <div key={index} className="grid grid-cols-[5rem_1fr_1fr] gap-4 border-b px-4 py-4 last:border-b-0 md:grid-cols-[6rem_1.4fr_1fr_6rem_9rem]">
          <span className="h-4 animate-pulse rounded-md bg-muted" />
          <span className="h-4 animate-pulse rounded-md bg-muted" />
          <span className="h-4 animate-pulse rounded-md bg-muted" />
          <span className="hidden h-4 animate-pulse rounded-md bg-muted md:block" />
          <span className="hidden h-4 animate-pulse rounded-md bg-muted md:block" />
        </div>
      ))}
    </div>
  )
}

function EmptyResults({
  title,
  description,
  action,
}: {
  title: string
  description: string
  action?: React.ReactNode
}) {
  return (
    <div className="flex min-h-64 flex-col items-center justify-center gap-3 px-4 text-center">
      <span className="flex size-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <DatabaseZap aria-hidden="true" className="size-5" />
      </span>
      <div className="flex max-w-md flex-col gap-1">
        <p className="font-medium">{title}</p>
        <p className="text-sm leading-relaxed text-muted-foreground">{description}</p>
      </div>
      {action}
    </div>
  )
}

function formatDate(value: string) {
  const [, month, day] = value.split('-')
  return `${Number(month)}月${Number(day)}日`
}

export function PlayerResults({
  playerName,
  playerTour,
  results,
  historyState,
  season,
  onSeasonChange,
  onRetry,
  seasons,
  tier,
  onTierChange,
  outcome,
  onOutcomeChange,
  page,
  onPageChange,
  total,
}: {
  playerName: string
  playerTour: TourKey | null
  results: PlayerResultPreview[]
  historyState: PlayerHistoryState
  season: number
  onSeasonChange: (season: number) => void
  onRetry: () => void
  /** Season selector values; defaults to the frozen v0 five-season list. */
  seasons?: number[]
  /**
   * Server-driven mode: the container owns tier/outcome/page state and
   * `results`/`total` are exactly the fetched page. Without `onPageChange`
   * the component keeps its v0 client-side filtering behavior.
   */
  tier?: 'ALL' | CompetitionTier
  onTierChange?: (tier: 'ALL' | CompetitionTier) => void
  outcome?: 'ALL' | MatchOutcome
  onOutcomeChange?: (outcome: 'ALL' | MatchOutcome) => void
  page?: number
  onPageChange?: (page: number) => void
  total?: number
}) {
  const [tierState, setTierState] = useState<'ALL' | CompetitionTier>('ALL')
  const [outcomeState, setOutcomeState] = useState<'ALL' | MatchOutcome>('ALL')
  const [pageState, setPageState] = useState(1)
  const pageSize = 20

  const serverMode = onPageChange !== undefined
  const activeTier = tier ?? tierState
  const activeOutcome = outcome ?? outcomeState
  const seasonList = seasons ?? seasonOptions

  function changeTier(next: 'ALL' | CompetitionTier) {
    if (onTierChange) onTierChange(next)
    else setTierState(next)
    changePage(1)
  }

  function changeOutcome(next: 'ALL' | MatchOutcome) {
    if (onOutcomeChange) onOutcomeChange(next)
    else setOutcomeState(next)
    changePage(1)
  }

  function changePage(next: number) {
    if (onPageChange) onPageChange(next)
    else setPageState(next)
  }

  const filteredResults = useMemo(() => {
    if (serverMode) return results
    const stateResults = historyState === 'partial' ? results.slice(0, 8) : results
    return stateResults.filter((result) => (
      result.season === season
      && (tierState === 'ALL' || result.tier === tierState)
      && (outcomeState === 'ALL' || result.outcome === outcomeState)
    ))
  }, [historyState, outcomeState, results, season, serverMode, tierState])

  const totalCount = serverMode ? (total ?? filteredResults.length) : filteredResults.length
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize))
  const currentPage = Math.min(serverMode ? (page ?? 1) : pageState, totalPages)
  const start = (currentPage - 1) * pageSize
  const visibleResults = serverMode ? filteredResults : filteredResults.slice(start, start + pageSize)
  const showResults = historyState === 'ready' || historyState === 'partial' || historyState === 'stale'

  function resetResultFilters() {
    changeTier('ALL')
    if (onOutcomeChange) onOutcomeChange('ALL')
    else setOutcomeState('ALL')
    changePage(1)
  }

  return (
    <Card aria-labelledby="player-results-title">
      <CardHeader className="border-b">
        <div>
          <CardTitle><h2 id="player-results-title">历史赛果</h2></CardTitle>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{playerName} · 最近五个赛季单打记录</p>
        </div>
        <CardAction><Badge variant="outline">20 / 页</Badge></CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-3 md:flex-row md:flex-wrap md:items-center">
          <FilterMenu
            label="赛季"
            value={season}
            options={seasonList.map((value) => ({ value, label: `${value} 赛季` }))}
            onChange={(value) => { onSeasonChange(value); changePage(1) }}
          />
          <FilterMenu
            label="赛事级别"
            value={activeTier}
            options={tierOptions}
            onChange={changeTier}
          />
          <FilterMenu
            label="赛果"
            value={activeOutcome}
            options={outcomeOptions}
            onChange={changeOutcome}
          />
          {(activeTier !== 'ALL' || activeOutcome !== 'ALL') ? (
            <Button type="button" variant="ghost" size="lg" onClick={resetResultFilters}>
              <RotateCcw data-icon="inline-start" aria-hidden="true" />
              重置赛果筛选
            </Button>
          ) : null}
          <p className="text-xs leading-relaxed text-muted-foreground md:ml-auto">
            {playerTour ?? ''}
            {playerTour ? ' 档案 · 不提供场地筛选' : '档案 · 不提供场地筛选'}
          </p>
        </div>

        {historyState === 'partial' ? (
          <div className="flex items-start gap-2 rounded-xl bg-premium/10 p-3 text-sm leading-relaxed text-foreground ring-1 ring-premium/20">
            <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-premium" />
            当前数据源只返回部分赛果；已显示可用记录。
          </div>
        ) : null}
        {historyState === 'stale' ? (
          <div className="flex items-start gap-2 rounded-xl bg-premium/10 p-3 text-sm leading-relaxed text-foreground ring-1 ring-premium/20">
            <Clock3 aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-premium" />
            正在显示最近一次成功快照；排名与赛果可能不是最新。
          </div>
        ) : null}
      </CardContent>

      <CardContent className="-mx-(--card-spacing) -mt-2">
        {historyState === 'loading' ? <LoadingResults /> : null}
        {historyState === 'empty' ? (
          <EmptyResults title="该赛季暂无赛果" description="当前赛季没有可展示的单打比赛记录。" />
        ) : null}
        {historyState === 'unavailable' ? (
          <EmptyResults title="历史数据暂不可用" description="该球员目前没有可用的历史赛果档案，请稍后再查看。" />
        ) : null}
        {historyState === 'error' ? (
          <div className="flex min-h-64 flex-col items-center justify-center gap-3 px-4 text-center" role="alert">
            <span className="flex size-12 items-center justify-center rounded-full bg-destructive/10 text-destructive">
              <AlertTriangle aria-hidden="true" className="size-5" />
            </span>
            <div className="flex max-w-md flex-col gap-1">
              <p className="font-medium">赛果加载失败</p>
              <p className="text-sm leading-relaxed text-muted-foreground">连接暂时中断，筛选条件已保留。</p>
            </div>
            <Button type="button" variant="outline" onClick={onRetry}>重试加载</Button>
          </div>
        ) : null}
        {showResults && visibleResults.length === 0 ? (
          <EmptyResults
            title="当前筛选暂无赛果"
            description="换一个赛季、赛事级别或赛果后再试。"
            action={<Button type="button" variant="outline" onClick={resetResultFilters}>清除赛果筛选</Button>}
          />
        ) : null}
        {showResults && visibleResults.length ? (
          <div role="region" aria-label={`${playerName} 历史赛果列表`}>
            <div className="hidden grid-cols-[6rem_minmax(0,1.35fr)_minmax(0,1fr)_6rem_9rem_1.5rem] items-center gap-4 border-y bg-muted/45 px-4 py-2.5 text-xs font-medium text-muted-foreground md:grid">
              <span>日期</span>
              <span>赛事 / 轮次</span>
              <span>对手</span>
              <span>结果</span>
              <span>比分</span>
              <span className="sr-only">查看</span>
            </div>
            <ol className="flex flex-col">
              {visibleResults.map((result) => (
                <li key={result.id}>
                  <Link
                    href={`/matches/${encodeURIComponent(result.matchId)}`}
                    aria-label={`查看 ${result.date} 对阵 ${result.opponent.name} 的比赛详情`}
                    className="group flex flex-col gap-3 border-b px-4 py-4 transition-colors last:border-b-0 hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring md:grid md:grid-cols-[6rem_minmax(0,1.35fr)_minmax(0,1fr)_6rem_9rem_1.5rem] md:items-center md:gap-4 md:py-3"
                  >
                    <time dateTime={result.date ?? undefined} className="font-mono text-xs text-muted-foreground">
                      {result.date ? formatDate(result.date) : '日期暂无'}
                    </time>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{result.tournament}</p>
                      {/* Keep v0's exact text-node split (part, separator, part, ...)
                          so glyph fallback and the visual baseline stay identical. */}
                      <p className="mt-0.5 truncate text-xs text-muted-foreground">
                        {(() => {
                          const parts = [result.tournamentZh, result.round, result.surface, result.tier]
                            .filter((part): part is string => Boolean(part))
                          return parts.map((part, index) => (
                            <Fragment key={index}>
                              {index > 0 ? ' · ' : ''}
                              {part}
                            </Fragment>
                          ))
                        })()}
                      </p>
                    </div>
                    <div className="flex min-w-0 items-center gap-2">
                      <PlayerCountry player={result.opponent} />
                      <div className="min-w-0">
                        <p className="truncate text-sm">{result.opponent.name}</p>
                        {result.opponent.nameZh ? <p className="truncate text-xs text-muted-foreground">{result.opponent.nameZh}</p> : null}
                      </div>
                    </div>
                    <Badge
                      variant="outline"
                      className={result.outcome === 'win' ? 'w-fit border-primary/25 bg-primary/10 text-primary' : 'w-fit text-muted-foreground'}
                    >
                      {result.outcome === 'win' ? '胜' : '负'}
                    </Badge>
                    <span className="font-mono text-sm font-semibold tabular-nums">{result.score ?? '比分暂无'}</span>
                    <ChevronRight aria-hidden="true" className="hidden size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-foreground md:block" />
                  </Link>
                </li>
              ))}
            </ol>
          </div>
        ) : null}
      </CardContent>

      {showResults && totalCount > 0 ? (
        <CardFooter className="flex-col gap-3 bg-muted/35 md:flex-row md:justify-between">
          <p className="font-mono text-xs text-muted-foreground" aria-live="polite">
            {start + 1}–{Math.min(start + pageSize, totalCount)} / 共 {totalCount} 场
          </p>
          <nav className="flex items-center gap-1" aria-label="历史赛果分页">
            <Button type="button" variant="ghost" size="sm" disabled={currentPage === 1} onClick={() => changePage(currentPage - 1)}>
              <ChevronLeft data-icon="inline-start" aria-hidden="true" />上一页
            </Button>
            <span className="px-2 font-mono text-xs text-muted-foreground">{currentPage} / {totalPages}</span>
            <Button type="button" variant="ghost" size="sm" disabled={currentPage === totalPages} onClick={() => changePage(currentPage + 1)}>
              下一页<ChevronRight data-icon="inline-end" aria-hidden="true" />
            </Button>
          </nav>
        </CardFooter>
      ) : null}
    </Card>
  )
}
