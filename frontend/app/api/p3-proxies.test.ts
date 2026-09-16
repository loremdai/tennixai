// @vitest-environment node
// P3 thin proxy contract tests (T67): every route forwards to the canonical
// backend path preserving query string, status and SSE headers; only GET is
// exported; routes are force-dynamic (zero caching) and hold no business
// state. Cancellation propagates because the upstream body is passed
// through untouched.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const BASE_URL = 'http://127.0.0.1:8000'

const REST_ROUTES: {
  name: string
  modulePath: string
  requestUrl: string
  expectedTarget: string
  context?: (request: Request) => unknown
}[] = [
  {
    name: 'markets',
    modulePath: './markets/route',
    requestUrl: 'http://local/api/markets?tier=atp&page=2&page_size=10',
    expectedTarget: `${BASE_URL}/api/v1/markets?tier=atp&page=2&page_size=10`,
  },
  {
    name: 'opportunities',
    modulePath: './markets/opportunities/route',
    requestUrl: 'http://local/api/markets/opportunities',
    expectedTarget: `${BASE_URL}/api/v1/markets/opportunities`,
  },
  {
    name: 'pulse',
    modulePath: './markets/pulse/route',
    requestUrl: 'http://local/api/markets/pulse',
    expectedTarget: `${BASE_URL}/api/v1/markets/pulse`,
  },
  {
    name: 'paper positions',
    modulePath: './paper/positions/route',
    requestUrl: 'http://local/api/paper/positions',
    expectedTarget: `${BASE_URL}/api/v1/paper/positions`,
  },
  {
    name: 'match decision',
    modulePath: './matches/[matchId]/decision/route',
    requestUrl: 'http://local/api/matches/mat_9/decision',
    expectedTarget: `${BASE_URL}/api/v1/matches/mat_9/decision`,
    context: () => ({ params: Promise.resolve({ matchId: 'mat_9' }) }),
  },
]

const STREAM_ROUTES: {
  name: string
  modulePath: string
  requestUrl: string
  expectedTarget: string
  context?: (request: Request) => unknown
}[] = [
  {
    name: 'markets stream',
    modulePath: './markets/stream/route',
    requestUrl: 'http://local/api/markets/stream',
    expectedTarget: `${BASE_URL}/api/v1/markets/stream`,
  },
  {
    name: 'decision stream',
    modulePath: './matches/[matchId]/decision/stream/route',
    requestUrl: 'http://local/api/matches/mat_9/decision/stream',
    expectedTarget: `${BASE_URL}/api/v1/matches/mat_9/decision/stream`,
    context: () => ({ params: Promise.resolve({ matchId: 'mat_9' }) }),
  },
]

beforeEach(() => {
  process.env.TENNIX_BACKEND_URL = BASE_URL
})

afterEach(() => {
  vi.unstubAllGlobals()
  delete process.env.TENNIX_BACKEND_URL
})

describe('P3 REST proxies', () => {
  it.each(REST_ROUTES)('$name forwards method, query string and status', async (route) => {
    const fetch = vi.fn().mockResolvedValue(
      Response.json({ data: [] }, { headers: { 'X-Request-ID': 'req-p3' } }),
    )
    vi.stubGlobal('fetch', fetch)
    const module = (await import(route.modulePath)) as Record<string, unknown>
    const GET = module.GET as (request: Request, context?: unknown) => Promise<Response>

    const request = new Request(route.requestUrl)
    const response = await GET(request, route.context?.(request))

    expect(fetch).toHaveBeenCalledTimes(1)
    const [target, init] = fetch.mock.calls[0]
    expect(String(target)).toBe(route.expectedTarget)
    expect(init.method).toBe('GET')
    expect(init.cache).toBe('no-store')
    expect(response.status).toBe(200)
    expect(response.headers.get('x-request-id')).toBe('req-p3')
  })

  it.each(REST_ROUTES)('$name passes through the typed 503 p3_disabled body', async (route) => {
    const body = JSON.stringify({
      error: { code: 'p3_disabled', message: 'P3 market decision support is disabled', details: {} },
      request_id: 'req-x',
    })
    const fetch = vi.fn().mockResolvedValue(
      new Response(body, { status: 503, headers: { 'Content-Type': 'application/json' } }),
    )
    vi.stubGlobal('fetch', fetch)
    const module = (await import(route.modulePath)) as Record<string, unknown>
    const GET = module.GET as (request: Request, context?: unknown) => Promise<Response>

    const request = new Request(route.requestUrl)
    const response = await GET(request, route.context?.(request))

    expect(response.status).toBe(503)
    expect((await response.json()).error.code).toBe('p3_disabled')
  })

  it.each([...REST_ROUTES, ...STREAM_ROUTES])('$name exports GET only and is force-dynamic', async (route) => {
    const module = (await import(route.modulePath)) as Record<string, unknown>
    expect(typeof module.GET).toBe('function')
    for (const verb of ['POST', 'PUT', 'PATCH', 'DELETE']) {
      expect(module[verb], verb).toBeUndefined()
    }
    expect(module.dynamic).toBe('force-dynamic')
    expect(module.runtime).toBe('nodejs')
  })
})

describe('P3 SSE proxies', () => {
  it.each(STREAM_ROUTES)(
    '$name preserves the stream body, SSE headers and Last-Event-ID',
    async (route) => {
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode('event: ready\ndata: {}\n\n'))
        },
      })
      const fetch = vi.fn().mockResolvedValue(
        new Response(stream, {
          status: 200,
          headers: {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache, no-transform',
            'X-Request-ID': 'req-sse',
          },
        }),
      )
      vi.stubGlobal('fetch', fetch)
      const module = (await import(route.modulePath)) as Record<string, unknown>
      const GET = module.GET as (request: Request, context?: unknown) => Promise<Response>

      const request = new Request(route.requestUrl, {
        headers: { Accept: 'text/event-stream', 'Last-Event-ID': '12' },
      })
      const response = await GET(request, route.context?.(request))

      const [target, init] = fetch.mock.calls[0]
      expect(String(target)).toBe(route.expectedTarget)
      expect(init.headers.get('Last-Event-ID')).toBe('12')
      // The upstream body is passed through untouched, so client
      // cancellation propagates to the proxied stream.
      expect(response.body).toBe(stream)
      expect(response.headers.get('content-type')).toBe('text/event-stream')
      expect(response.headers.get('cache-control')).toBe('no-cache, no-transform')
    },
  )
})
