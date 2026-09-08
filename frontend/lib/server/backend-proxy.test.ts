// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { proxyBackend } from './backend-proxy'

const BASE_URL = 'http://127.0.0.1:8000'

beforeEach(() => {
  process.env.TENNIX_BACKEND_URL = BASE_URL
})

afterEach(() => {
  vi.unstubAllGlobals()
  delete process.env.TENNIX_BACKEND_URL
})

function fetchMock() {
  return vi.fn()
}

describe('proxyBackend', () => {
  it('preserves SSE without reading the upstream body', async () => {
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('event: done\ndata: {}\n\n'))
      },
    })
    const fetch = fetchMock().mockResolvedValue(
      new Response(stream, {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream', 'X-Request-ID': 'req-1' },
      }),
    )
    vi.stubGlobal('fetch', fetch)

    const response = await proxyBackend(
      new Request('http://local/api/chat/stream', {
        method: 'POST',
        body: '{"scope":"global","messages":[]}',
      }),
      '/api/v1/chat/stream',
    )

    expect(response.body).toBe(stream)
    expect(response.status).toBe(200)
    expect(response.headers.get('content-type')).toBe('text/event-stream')
    expect(response.headers.get('x-request-id')).toBe('req-1')
  })

  it('forwards method, query string, and content type to the backend', async () => {
    const fetch = fetchMock().mockResolvedValue(
      Response.json({ data: [] }, { headers: { 'X-Request-ID': 'req-2' } }),
    )
    vi.stubGlobal('fetch', fetch)

    const response = await proxyBackend(
      new Request('http://local/api/matches?status=live&player=Sinner'),
      '/api/v1/matches',
    )

    expect(fetch).toHaveBeenCalledTimes(1)
    const [target, init] = fetch.mock.calls[0]
    expect(String(target)).toBe(`${BASE_URL}/api/v1/matches?status=live&player=Sinner`)
    expect(init.method).toBe('GET')
    expect(init.cache).toBe('no-store')
    expect(response.status).toBe(200)
    expect(await response.json()).toEqual({ data: [] })
  })

  it('preserves 429 status and Retry-After', async () => {
    const fetch = fetchMock().mockResolvedValue(
      new Response(JSON.stringify({ error: { code: 'rate_limited', message: 'slow down', details: {} } }), {
        status: 429,
        headers: { 'Content-Type': 'application/json', 'Retry-After': '30' },
      }),
    )
    vi.stubGlobal('fetch', fetch)

    const response = await proxyBackend(
      new Request('http://local/api/matches?status=live'),
      '/api/v1/matches',
    )

    expect(response.status).toBe(429)
    expect(response.headers.get('retry-after')).toBe('30')
    expect(response.headers.get('content-type')).toBe('application/json')
  })

  it('does not forward authorization or cookie headers but keeps request id', async () => {
    const fetch = fetchMock().mockResolvedValue(Response.json({ data: [] }))
    vi.stubGlobal('fetch', fetch)

    await proxyBackend(
      new Request('http://local/api/matches?status=live', {
        headers: {
          Authorization: 'Bearer secret-token',
          Cookie: 'session=abc',
          'X-Request-ID': 'req-3',
          'Content-Type': 'application/json',
        },
      }),
      '/api/v1/matches',
    )

    const [, init] = fetch.mock.calls[0]
    const headers = new Headers(init.headers)
    expect(headers.get('authorization')).toBeNull()
    expect(headers.get('cookie')).toBeNull()
    expect(headers.get('x-request-id')).toBe('req-3')
  })

  it('translates fetch rejection into typed internal_error with 502', async () => {
    const fetch = fetchMock().mockRejectedValue(new Error('ECONNREFUSED'))
    vi.stubGlobal('fetch', fetch)

    const response = await proxyBackend(
      new Request('http://local/api/matches?status=live'),
      '/api/v1/matches',
    )

    expect(response.status).toBe(502)
    const body = await response.json()
    expect(body.error.code).toBe('internal_error')
    expect(response.headers.get('content-type')).toContain('application/json')
  })

  it('returns 500 internal_error when the backend URL is not configured', async () => {
    delete process.env.TENNIX_BACKEND_URL
    const fetch = fetchMock()
    vi.stubGlobal('fetch', fetch)

    const response = await proxyBackend(
      new Request('http://local/api/matches?status=live'),
      '/api/v1/matches',
    )

    expect(fetch).not.toHaveBeenCalled()
    expect(response.status).toBe(500)
    expect((await response.json()).error.code).toBe('internal_error')
  })

  it('never exposes the backend base URL in the response', async () => {
    const fetch = fetchMock().mockResolvedValue(
      Response.json({ error: { code: 'not_found', message: 'Match not found', details: {} } }, { status: 404 }),
    )
    vi.stubGlobal('fetch', fetch)

    const response = await proxyBackend(
      new Request('http://local/api/matches/mat_missing'),
      '/api/v1/matches/mat_missing',
    )

    const text = await response.text()
    expect(text).not.toContain(BASE_URL)
    expect(text).not.toContain('8000')
    for (const [, value] of response.headers.entries()) {
      expect(value).not.toContain(BASE_URL)
    }
  })

  it('streams POST bodies without buffering', async () => {
    const fetch = fetchMock().mockResolvedValue(Response.json({ ok: true }))
    vi.stubGlobal('fetch', fetch)

    const body = '{"scope":"match","match_id":"mat_1","messages":[{"role":"user","content":"谁在发球？"}]}'
    await proxyBackend(
      new Request('http://local/api/chat/stream', {
        method: 'POST',
        body,
        headers: { 'Content-Type': 'application/json' },
      }),
      '/api/v1/chat/stream',
    )

    const [, init] = fetch.mock.calls[0]
    expect(init.method).toBe('POST')
    expect(init.duplex).toBe('half')
    expect(init.body).toBeInstanceOf(ReadableStream)
  })
})
