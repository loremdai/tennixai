import type { Metadata } from 'next'

import { MatchPage } from '@/components/match-page'
import type { MatchStatus } from '@/components/match/match-data'

export const metadata: Metadata = {
  title: 'Sinner 对阵 Alcaraz 比赛智能',
  description: '预览赛前、直播与完赛状态，并通过 Tennix AI 理解比分、技术统计和比赛进程。',
}

type PageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}

const validStatuses = new Set<MatchStatus>(['upcoming', 'live', 'finished'])

export default async function Page({ searchParams }: PageProps) {
  const params = await searchParams
  const rawStatus = Array.isArray(params.status) ? params.status[0] : params.status
  const initialStatus = rawStatus && validStatuses.has(rawStatus as MatchStatus)
    ? rawStatus as MatchStatus
    : 'upcoming'

  return <MatchPage initialStatus={initialStatus} />
}
