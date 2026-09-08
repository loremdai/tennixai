import type { NextRequest } from 'next/server'

import { proxyBackend } from '@/lib/server/backend-proxy'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function POST(request: NextRequest) {
  return proxyBackend(request, '/api/v1/chat/stream')
}
