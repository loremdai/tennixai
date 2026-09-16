import { MarketsPage } from '@/components/markets/markets-page'
import {
  parseGenderFilter,
  parseMarketsState,
  parseMarketView,
  parsePhaseFilter,
  parseTierFilters,
} from '@/components/p3/p3-preview-data'

type PageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}

export default async function Page({ searchParams }: PageProps) {
  const params = await searchParams

  return (
    <MarketsPage
      initialView={parseMarketView(params.view)}
      initialState={parseMarketsState(params.state)}
      initialTiers={parseTierFilters(params.tier)}
      initialGender={parseGenderFilter(params.gender)}
      initialPhase={parsePhaseFilter(params.phase)}
    />
  )
}
