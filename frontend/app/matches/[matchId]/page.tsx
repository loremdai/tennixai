import type { Metadata } from 'next'

import { MatchPage } from '@/components/match-page'

export const metadata: Metadata = {
  title: '比赛智能 · Tennix',
  description: '查看单场比赛的赛况、比分和比赛助手。',
}

type PageProps = {
  params: Promise<{ matchId: string }>
}

export default async function Page({ params }: PageProps) {
  const { matchId } = await params

  return <MatchPage matchId={matchId} />
}
