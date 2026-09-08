import type { Metadata } from 'next'

import { MatchPage } from '@/components/match-page'
import type { MatchStatus } from '@/components/match/match-data'
import { buildPreviewMatch } from '@/components/match/match-preview-data'

export const metadata: Metadata = {
  title: '比赛状态预览 · Tennix',
  description: '原型视觉预览路由：赛前、直播与完赛状态的样例展示，不连接真实数据。',
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

  return <MatchPage previewMatch={buildPreviewMatch(initialStatus)} preview />
}
