import type { Metadata } from 'next'

import {
  getPlayerProfileBundle,
  type PlayerHistoryState,
  type ProfileStatusKey,
} from '@/components/players/player-preview-data'
import { PlayerProfileLive } from '@/components/players/player-profile-live'
import { PlayerProfilePage } from '@/components/players/player-profile-page'

type PlayerRouteParams = Promise<{ playerId: string }>
type PlayerSearchParams = Promise<Record<string, string | string[] | undefined>>

const historyStates: PlayerHistoryState[] = [
  'ready',
  'empty',
  'partial',
  'unavailable',
  'loading',
  'error',
  'stale',
]

const profileStatuses: ProfileStatusKey[] = ['live', 'next', 'none']

function firstValue(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value
}

function isPreview(searchParams: Record<string, string | string[] | undefined>) {
  return firstValue(searchParams.preview) === '1'
}

export async function generateMetadata({
  params,
  searchParams,
}: {
  params: PlayerRouteParams
  searchParams: PlayerSearchParams
}): Promise<Metadata> {
  const [{ playerId }, query] = await Promise.all([params, searchParams])
  if (!isPreview(query)) {
    return {
      title: '球员资料 | Tennix AI',
      description: '查看球员的排名、赛季摘要、当前比赛状态与最近五个赛季单打赛果。',
    }
  }
  const bundle = getPlayerProfileBundle(playerId)
  const profile = bundle.scenarios.find((scenario) => scenario.profile.id === bundle.currentPlayerId)?.profile
  return {
    title: `${profile?.name ?? '球员资料'} | Tennix AI`,
    description: `查看 ${profile?.name ?? '球员'} 的排名、赛季摘要、当前比赛状态与最近五个赛季单打赛果。`,
  }
}

export default async function PlayerProfileRoute({
  params,
  searchParams,
}: {
  params: PlayerRouteParams
  searchParams: PlayerSearchParams
}) {
  const [{ playerId }, query] = await Promise.all([params, searchParams])

  if (!isPreview(query)) {
    return <PlayerProfileLive playerId={playerId} />
  }

  // Frozen v0 visual truth: deterministic preview scenarios, no production APIs.
  const bundle = getPlayerProfileBundle(playerId)
  const currentScenario = bundle.scenarios.find((scenario) => scenario.profile.id === bundle.currentPlayerId)
  const requestedStatus = firstValue(query.status) as ProfileStatusKey | undefined
  const requestedHistory = firstValue(query.history) as PlayerHistoryState | undefined
  const initialStatus = requestedStatus && profileStatuses.includes(requestedStatus)
    ? requestedStatus
    : currentScenario?.defaultStatus ?? 'none'
  const initialHistoryState = requestedHistory && historyStates.includes(requestedHistory)
    ? requestedHistory
    : currentScenario?.defaultHistoryState ?? 'unavailable'

  return (
    <PlayerProfilePage
      bundle={bundle}
      initialStatus={initialStatus}
      initialHistoryState={initialHistoryState}
    />
  )
}
