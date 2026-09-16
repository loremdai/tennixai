import { MarketsPage } from '@/components/markets/markets-page'
import { MarketsWorkspace } from '@/components/markets/markets-state'
import {
  parseGenderFilter,
  parseMarketsState,
  parseMarketView,
  parsePhaseFilter,
  parseTierFilters,
} from '@/components/p3/p3-preview-data'
import type { MarketsTabValue } from '@/components/markets/markets-tabs'
import type { GenderFilter, PhaseFilter } from '@/components/markets/market-filters'
import type { CircuitTier } from '@/lib/api/types'

type PageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}

const VIEWS = ['opportunities', 'all', 'paper'] as const
const TIERS = ['atp', 'wta', 'challenger', 'itf', 'other'] as const
const GENDERS = ['men', 'women', 'mixed', 'unknown'] as const
const PHASES = ['prematch', 'live', 'closed'] as const

function firstValue(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value
}

function parseProductionView(value: string | string[] | undefined): MarketsTabValue {
  const candidate = firstValue(value)
  return (VIEWS as readonly string[]).includes(candidate ?? '')
    ? (candidate as MarketsTabValue)
    : 'opportunities'
}

function parseProductionTiers(value: string | string[] | undefined): CircuitTier[] {
  const values = Array.isArray(value) ? value : value ? [value] : []
  return values.filter((tier): tier is CircuitTier =>
    (TIERS as readonly string[]).includes(tier),
  )
}

function parseProductionGender(
  value: string | string[] | undefined,
): GenderFilter {
  const candidate = firstValue(value)
  return (GENDERS as readonly string[]).includes(candidate ?? '')
    ? (candidate as GenderFilter)
    : 'all'
}

function parseProductionPhase(
  value: string | string[] | undefined,
): PhaseFilter {
  const candidate = firstValue(value)
  return (PHASES as readonly string[]).includes(candidate ?? '')
    ? (candidate as PhaseFilter)
    : 'all'
}

export default async function Page({ searchParams }: PageProps) {
  const params = await searchParams

  // The frozen T56 prototype stays the visual truth under ?preview=p3;
  // every other visit gets the production workspace on canonical APIs.
  if (firstValue(params.preview) === 'p3') {
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

  return (
    <MarketsWorkspace
      initialView={parseProductionView(params.view)}
      initialTiers={parseProductionTiers(params.tier)}
      initialGender={parseProductionGender(params.gender)}
      initialPhase={parseProductionPhase(params.phase)}
    />
  )
}
