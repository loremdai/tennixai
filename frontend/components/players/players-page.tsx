'use client'

import { useMemo, useState } from 'react'

import { PlayerSearchResults } from '@/components/players/player-search-results'
import {
  searchPlayerDirectory,
  type CountryPreview,
  type PlayerDirectoryEntry,
  type TourKey,
} from '@/components/players/player-preview-data'
import {
  PlayersDirectoryShell,
  replaceDirectoryUrl,
  type PlayersFilters,
} from '@/components/players/players-directory-shell'
import { RankingsTable } from '@/components/players/rankings-table'

export type { PlayersFilters }

/**
 * Preview container: renders the frozen v0 page from deterministic local
 * data only. Production wiring lives in `players-directory-live.tsx`.
 */
export function PlayersPage({
  rankings,
  directory,
  countries,
  initialFilters,
}: {
  rankings: Record<TourKey, PlayerDirectoryEntry[]>
  directory: PlayerDirectoryEntry[]
  countries: CountryPreview[]
  initialFilters: PlayersFilters
}) {
  const [filters, setFilters] = useState(initialFilters)
  const [searchValue, setSearchValue] = useState(initialFilters.query)

  const selectedCountry = countries.find((country) => country.code === filters.countryCode)
  const filteredRankings = useMemo(
    () => rankings[filters.tour].filter((player) => (
      filters.countryCode === 'ALL' || player.countryCode === filters.countryCode
    )),
    [filters.countryCode, filters.tour, rankings],
  )
  const searchResults = useMemo(
    () => searchPlayerDirectory(directory, {
      query: filters.query,
      countryCode: filters.countryCode,
    }),
    [directory, filters.countryCode, filters.query],
  )

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
    const next = { tour: 'ATP' as const, countryCode: 'ALL', query: '', page: 1 }
    setSearchValue('')
    applyFilters(next)
  }

  return (
    <PlayersDirectoryShell
      headerNote="PREVIEW · 2026-09-11"
      filters={filters}
      searchValue={searchValue}
      countries={countries}
      onSearchValueChange={setSearchValue}
      onTourChange={selectTour}
      onCountryChange={selectCountry}
      onSubmitSearch={submitSearch}
      onClearSearch={clearSearch}
      onQuickSearch={runQuickSearch}
      onReset={resetFilters}
    >
      {filters.query ? (
        <PlayerSearchResults
          query={filters.query}
          countryName={selectedCountry?.name ?? null}
          players={searchResults}
          onClear={clearSearch}
        />
      ) : (
        <RankingsTable
          tour={filters.tour}
          players={filteredRankings}
          page={filters.page}
          pageSize={50}
          onPageChange={(page) => applyFilters({ ...filters, page })}
        />
      )}
    </PlayersDirectoryShell>
  )
}
