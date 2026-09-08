import type { Metadata } from 'next'

import { MatchPage } from '@/components/match-page'

export const metadata: Metadata = {
  title: '比赛智能 · Tennix',
  description: '基于 Tennix 内部比赛 ID 的单场比赛事实、比分与上下文问答。',
}

type PageProps = {
  params: Promise<{ matchId: string }>
}

export default async function Page({ params }: PageProps) {
  const { matchId } = await params

  return <MatchPage matchId={matchId} />
}
