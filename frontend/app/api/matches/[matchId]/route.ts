import type { NextRequest } from 'next/server'

import { proxyBackend } from '@/lib/server/backend-proxy'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ matchId: string }> },
) {
  const { matchId } = await params
  return proxyBackend(request, `/api/v1/matches/${encodeURIComponent(matchId)}`)
}
