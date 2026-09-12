'use client'

import type { FormEvent, KeyboardEvent, ReactNode } from 'react'
import { Check, ChevronDown, RotateCcw, Search, X } from 'lucide-react'

import { ProductHeader } from '@/components/match/match-header'
import type { CountryPreview, TourKey } from '@/components/players/player-preview-data'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'

export type PlayersFilters = {
  tour: TourKey
  countryCode: string
  query: string
  page: number
}

export const quickSearches: Array<{ label: string; query: string; tour: TourKey }> = [
  { label: 'Ben Shelton', query: 'Ben Shelton', tour: 'ATP' },
  { label: 'B. Shelton', query: 'B. Shelton', tour: 'ATP' },
  { label: '郑钦文', query: '郑钦文', tour: 'WTA' },
  { label: '排名 201', query: 'Coleman Wong', tour: 'ATP' },
  { label: '暂无当前排名', query: 'Bryan Shelton', tour: 'ATP' },
]

export function replaceDirectoryUrl(filters: PlayersFilters) {
  const params = new URLSearchParams()
  // Keep the preview switch sticky across interactions so a reload stays in
  // the mode the user (or a visual baseline) started from.
  if (typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('preview') === '1') {
    params.set('preview', '1')
  }
  if (filters.tour !== 'ATP') params.set('tour', filters.tour)
  if (filters.countryCode !== 'ALL') params.set('country', filters.countryCode)
  if (filters.query) params.set('q', filters.query)
  if (filters.page > 1 && !filters.query) params.set('page', String(filters.page))
  const search = params.toString()
  window.history.replaceState(null, '', `/players${search ? `?${search}` : ''}`)
}

/**
 * Shared v0 page shell for `/players`: header, tour tabs, country filters,
 * search form and quick chips. The preview and production containers pass
 * their own results area as `children`; the frozen visual structure lives
 * here so both modes stay pixel-identical.
 */
export function PlayersDirectoryShell({
  headerNote,
  filters,
  searchValue,
  countries,
  onSearchValueChange,
  onTourChange,
  onCountryChange,
  onSubmitSearch,
  onClearSearch,
  onQuickSearch,
  onReset,
  children,
}: {
  headerNote: string
  filters: PlayersFilters
  searchValue: string
  countries: CountryPreview[]
  onSearchValueChange: (value: string) => void
  onTourChange: (tour: TourKey) => void
  onCountryChange: (countryCode: string) => void
  onSubmitSearch: () => void
  onClearSearch: () => void
  onQuickSearch: (query: string, tour: TourKey) => void
  onReset: () => void
  children: ReactNode
}) {
  const selectedCountry = countries.find((country) => country.code === filters.countryCode)

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    onSubmitSearch()
  }

  function guardComposition(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter' && (event.nativeEvent.isComposing || event.keyCode === 229)) {
      event.preventDefault()
    }
  }

  return (
    <div className="min-h-dvh bg-background text-foreground">
      <ProductHeader active="players" />
      <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 md:px-6 md:py-8">
        <section className="flex flex-col gap-3" aria-labelledby="players-page-title">
          <p className="font-mono text-xs font-semibold tracking-[0.18em] text-primary">PLAYER DIRECTORY</p>
          <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
            <div className="flex max-w-2xl flex-col gap-2">
              <h1 id="players-page-title" className="text-balance text-3xl font-semibold tracking-tight md:text-4xl">
                球员与世界排名
              </h1>
              <p className="text-pretty text-sm leading-relaxed text-muted-foreground md:text-base">
                浏览 ATP 与 WTA 单打 Top 200，并按英文名、中文名或常用缩写搜索完整球员目录。
              </p>
            </div>
            <p className="font-mono text-xs text-muted-foreground">{headerNote}</p>
          </div>
        </section>

        <section className="flex flex-col gap-4 rounded-xl bg-card p-4 ring-1 ring-foreground/10 md:p-5" aria-label="球员目录筛选">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex w-fit rounded-xl bg-muted p-1" role="tablist" aria-label="巡回赛">
              {(['ATP', 'WTA'] as const).map((tour) => (
                <Button
                  key={tour}
                  type="button"
                  role="tab"
                  size="lg"
                  variant={filters.tour === tour ? 'default' : 'ghost'}
                  aria-selected={filters.tour === tour}
                  onClick={() => onTourChange(tour)}
                  className="min-w-24"
                >
                  {tour}
                </Button>
              ))}
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <DropdownMenu>
                <DropdownMenuTrigger
                  render={<Button variant="outline" size="lg" aria-label="选择国家或地区" />}
                >
                  {selectedCountry?.flagUrl ? (
                    <img src={selectedCountry.flagUrl} alt="" className="h-3.5 w-5 rounded-sm object-cover ring-1 ring-border" />
                  ) : null}
                  {selectedCountry?.name ?? '全部国家/地区'}
                  <ChevronDown data-icon="inline-end" aria-hidden="true" />
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="min-w-56">
                  <DropdownMenuGroup>
                    <DropdownMenuLabel>国家 / 地区</DropdownMenuLabel>
                    <DropdownMenuItem onClick={() => onCountryChange('ALL')}>
                      <span className="flex size-4 items-center justify-center">
                        {filters.countryCode === 'ALL' ? <Check aria-hidden="true" /> : null}
                      </span>
                      全部国家/地区
                    </DropdownMenuItem>
                  </DropdownMenuGroup>
                  <DropdownMenuSeparator />
                  <DropdownMenuGroup>
                    {countries.map((item) => (
                      <DropdownMenuItem key={item.code} onClick={() => onCountryChange(item.code)}>
                        <span className="flex size-4 items-center justify-center">
                          {filters.countryCode === item.code ? <Check aria-hidden="true" /> : null}
                        </span>
                        {item.flagUrl ? <img src={item.flagUrl} alt="" className="h-3.5 w-5 rounded-sm object-cover ring-1 ring-border" /> : null}
                        <span>{item.name}</span>
                        <span className="ml-auto font-mono text-xs text-muted-foreground">{item.code}</span>
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuGroup>
                </DropdownMenuContent>
              </DropdownMenu>

              <Button
                type="button"
                size="lg"
                variant={filters.countryCode === 'CHN' ? 'default' : 'outline'}
                aria-pressed={filters.countryCode === 'CHN'}
                onClick={() => onCountryChange(filters.countryCode === 'CHN' ? 'ALL' : 'CHN')}
              >
                仅看中国球员
              </Button>

              {(filters.countryCode !== 'ALL' || filters.query || filters.tour !== 'ATP') ? (
                <Button type="button" size="lg" variant="ghost" onClick={onReset}>
                  <RotateCcw data-icon="inline-start" aria-hidden="true" />
                  重置
                </Button>
              ) : null}
            </div>
          </div>

          <form onSubmit={submitSearch} className="relative">
            <label htmlFor="player-directory-search" className="sr-only">搜索球员</label>
            <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="player-directory-search"
              value={searchValue}
              onChange={(event) => onSearchValueChange(event.target.value)}
              onKeyDown={guardComposition}
              placeholder="搜索 Ben Shelton、Shelton、B. Shelton 或郑钦文"
              autoComplete="off"
              className="h-11 bg-background pl-10 pr-11"
            />
            {searchValue ? (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={onClearSearch}
                aria-label="清空球员搜索"
                className="absolute right-1.5 top-1.5"
              >
                <X aria-hidden="true" />
              </Button>
            ) : null}
            <button type="submit" className="sr-only">搜索球员</button>
          </form>

          <div className="flex flex-wrap items-center gap-2" aria-label="预览搜索示例">
            <span className="text-xs text-muted-foreground">试试</span>
            {quickSearches.map((item) => (
              <Button
                key={item.label}
                type="button"
                variant="secondary"
                size="xs"
                onClick={() => onQuickSearch(item.query, item.tour)}
              >
                {item.label}
              </Button>
            ))}
          </div>
        </section>

        {children}
      </main>
    </div>
  )
}
