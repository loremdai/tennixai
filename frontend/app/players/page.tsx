import type { Metadata } from 'next'

import {
  PLAYER_COUNTRY_OPTIONS,
  PLAYER_DIRECTORY,
  PLAYER_RANKINGS,
  type TourKey,
} from '@/components/players/player-preview-data'
import { PlayersDirectoryLive } from '@/components/players/players-directory-live'
import { PlayersPage } from '@/components/players/players-page'
import { PRODUCTION_COUNTRY_OPTIONS } from '@/lib/player-view-models'

export const metadata: Metadata = {
  title: '球员与世界排名 | Tennix AI',
  description: '浏览 ATP 与 WTA 单打世界排名，并通过英文名、中文名或缩写搜索球员。',
}

type PlayersSearchParams = Promise<Record<string, string | string[] | undefined>>

function firstValue(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value
}

export default async function PlayersRoute({ searchParams }: { searchParams: PlayersSearchParams }) {
  const params = await searchParams
  const preview = firstValue(params.preview) === '1'
  const tour: TourKey = firstValue(params.tour) === 'WTA' ? 'WTA' : 'ATP'
  const requestedCountry = firstValue(params.country) ?? 'ALL'
  const countryOptions = preview ? PLAYER_COUNTRY_OPTIONS : PRODUCTION_COUNTRY_OPTIONS
  const countryCode = countryOptions.some((country) => country.code === requestedCountry)
    ? requestedCountry
    : 'ALL'
  const requestedPage = Number(firstValue(params.page) ?? '1')
  const page = Number.isInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1
  const query = firstValue(params.q) ?? ''

  if (preview) {
    // Frozen v0 visual truth: deterministic preview data, no production APIs.
    return (
      <PlayersPage
        rankings={PLAYER_RANKINGS}
        directory={PLAYER_DIRECTORY}
        countries={PLAYER_COUNTRY_OPTIONS}
        initialFilters={{ tour, countryCode, query, page }}
      />
    )
  }

  return <PlayersDirectoryLive initialFilters={{ tour, countryCode, query, page }} />
}
