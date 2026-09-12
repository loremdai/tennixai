'use client'

import { useEffect, useState } from 'react'
import { AlertTriangle, Clock3, RotateCcw } from 'lucide-react'

import { PlayerSearchResults } from '@/components/players/player-search-results'
import type { PlayerDirectoryEntry, TourKey } from '@/components/players/player-preview-data'
import {
  PlayersDirectoryShell,
  replaceDirectoryUrl,
  type PlayersFilters,
} from '@/components/players/players-directory-shell'
import { RankingsTable } from '@/components/players/rankings-table'
import { Button } from '@/components/ui/button'
import { ApiError, getPlayerRankings, searchPlayerDirectory } from '@/lib/api/client'
import type { PlayerSearchResolutionDto, RankingPageDto } from '@/lib/api/types'
import {
  PRODUCTION_COUNTRY_OPTIONS,
  rankingsAvailabilityNotice,
  rankingsSnapshotNote,
  searchResolutionToEntries,
  toDirectoryEntry,
} from '@/lib/player-view-models'

type DirectoryDataState =
  | { phase: 'loading' }
  | { phase: 'error'; message: string }
  | { phase: 'rankings'; data: RankingPageDto }
  | { phase: 'search'; resolution: PlayerSearchResolutionDto; entries: PlayerDirectoryEntry[] }

function DirectorySkeleton() {
  return (
    <section
      className="flex flex-col gap-3 rounded-xl bg-card p-4 ring-1 ring-foreground/10 md:p-5"
      aria-label="正在加载球员目录"
      aria-busy="true"
    >
      <span className="sr-only">正在加载球员目录</span>
      {Array.from({ length: 8 }, (_, index) => (
        <div key={index} className="grid grid-cols-[3rem_minmax(0,1fr)_6rem] items-center gap-4">
          <span className="h-4 animate-pulse rounded-md bg-muted" />
          <span className="h-4 animate-pulse rounded-md bg-muted" />
          <span className="h-4 animate-pulse rounded-md bg-muted" />
        </div>
      ))}
    </section>
  )
}

function DirectoryErrorPanel({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10 md:p-5">
      <div className="flex min-h-64 flex-col items-center justify-center gap-3 text-center" role="alert">
        <span className="flex size-12 items-center justify-center rounded-full bg-destructive/10 text-destructive">
          <AlertTriangle aria-hidden="true" className="size-5" />
        </span>
        <div className="flex max-w-md flex-col gap-1">
          <p className="font-medium">球员目录加载失败</p>
          <p className="text-sm leading-relaxed text-muted-foreground">{message}</p>
        </div>
        <Button type="button" variant="outline" onClick={onRetry}>重试加载</Button>
      </div>
    </section>
  )
}

function DirectoryUnavailablePanel({ onRetry }: { onRetry: () => void }) {
  return (
    <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10 md:p-5">
      <div className="flex min-h-64 flex-col items-center justify-center gap-3 text-center">
        <span className="flex size-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <Clock3 aria-hidden="true" className="size-5" />
        </span>
        <div className="flex max-w-md flex-col gap-1">
          <p className="font-medium">排名暂不可用</p>
          <p className="text-sm leading-relaxed text-muted-foreground">
            本地目录还没有可用的排名快照；请先完成目录同步，或稍后重试。
          </p>
        </div>
        <Button type="button" variant="outline" onClick={onRetry}>
          <RotateCcw data-icon="inline-start" aria-hidden="true" />
          重试加载
        </Button>
      </div>
    </section>
  )
}

function AvailabilityNotice({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-2 rounded-xl bg-premium/10 p-3 text-sm leading-relaxed text-foreground ring-1 ring-premium/20">
      <Clock3 aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-premium" />
      {text}
    </div>
  )
}

/**
 * Production container for `/players`: consumes the versioned REST player
 * directory APIs through the same-origin proxies and renders the frozen v0
 * structure. URL query (`tour`, `country`, `q`, `page`) stays restorable.
 */
export function PlayersDirectoryLive({ initialFilters }: { initialFilters: PlayersFilters }) {
  const [filters, setFilters] = useState(initialFilters)
  const [searchValue, setSearchValue] = useState(initialFilters.query)
  const [state, setState] = useState<DirectoryDataState>({ phase: 'loading' })
  const [retryKey, setRetryKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setState({ phase: 'loading' })
    const task = filters.query
      ? searchPlayerDirectory(filters.query, 20, controller.signal).then((resolution) => {
          if (controller.signal.aborted) return
          let entries = searchResolutionToEntries(resolution)
          if (filters.countryCode !== 'ALL') {
            entries = entries.filter((entry) => entry.countryCode === filters.countryCode)
          }
          setState({ phase: 'search', resolution, entries })
        })
      : getPlayerRankings(
          {
            tour: filters.tour,
            page: filters.page,
            country: filters.countryCode === 'ALL' ? undefined : filters.countryCode,
          },
          controller.signal,
        ).then((data) => {
          if (controller.signal.aborted) return
          setState({ phase: 'rankings', data })
        })

    task.catch((error: unknown) => {
      if (controller.signal.aborted) return
      const message =
        error instanceof ApiError && error.message ? error.message : '无法连接到球员目录服务，请稍后重试。'
      setState({ phase: 'error', message })
    })

    return () => controller.abort()
  }, [filters.tour, filters.page, filters.countryCode, filters.query, retryKey])

  function applyFilters(next: PlayersFilters) {
    setFilters(next)
    replaceDirectoryUrl(next)
  }

  function selectTour(tour: TourKey) {
    applyFilters({ ...filters, tour, page: 1 })
  }

  function selectCountry(countryCode: string) {
    applyFilters({ ...filters, countryCode, page: 1 })
  }

  function submitSearch() {
    applyFilters({ ...filters, query: searchValue.trim(), page: 1 })
  }

  function clearSearch() {
    setSearchValue('')
    applyFilters({ ...filters, query: '', page: 1 })
  }

  function runQuickSearch(query: string, tour: TourKey) {
    setSearchValue(query)
    applyFilters({ ...filters, tour, query, page: 1 })
  }

  function resetFilters() {
    setSearchValue('')
    applyFilters({ tour: 'ATP', countryCode: 'ALL', query: '', page: 1 })
  }

  function retry() {
    setRetryKey((key) => key + 1)
  }

  const selectedCountry = PRODUCTION_COUNTRY_OPTIONS.find((country) => country.code === filters.countryCode)
  const headerNote =
    state.phase === 'rankings' ? rankingsSnapshotNote(state.data.as_of) : 'LIVE DATA'

  return (
    <PlayersDirectoryShell
      headerNote={headerNote}
      filters={filters}
      searchValue={searchValue}
      countries={PRODUCTION_COUNTRY_OPTIONS}
      onSearchValueChange={setSearchValue}
      onTourChange={selectTour}
      onCountryChange={selectCountry}
      onSubmitSearch={submitSearch}
      onClearSearch={clearSearch}
      onQuickSearch={runQuickSearch}
      onReset={resetFilters}
    >
      {state.phase === 'loading' ? <DirectorySkeleton /> : null}
      {state.phase === 'error' ? (
        <DirectoryErrorPanel message={state.message} onRetry={retry} />
      ) : null}
      {state.phase === 'rankings' ? (
        state.data.availability === 'unavailable' && state.data.entries.length === 0 ? (
          <DirectoryUnavailablePanel onRetry={retry} />
        ) : (
          <div className="flex flex-col gap-4">
            {rankingsAvailabilityNotice(state.data.availability) ? (
              <AvailabilityNotice text={rankingsAvailabilityNotice(state.data.availability) ?? ''} />
            ) : null}
            <RankingsTable
              tour={state.data.tour}
              players={state.data.entries.map(toDirectoryEntry)}
              page={state.data.page}
              pageSize={state.data.page_size}
              total={state.data.total}
              dataSourceNote={null}
              onPageChange={(page) => applyFilters({ ...filters, page })}
            />
          </div>
        )
      ) : null}
      {state.phase === 'search' ? (
        <PlayerSearchResults
          query={filters.query}
          countryName={selectedCountry?.name ?? null}
          players={state.entries}
          onClear={clearSearch}
        />
      ) : null}
    </PlayersDirectoryShell>
  )
}
