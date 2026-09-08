// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, getMatch, getMatches, getPlayers, parseSse, streamChat } from './client'
import type { ChatEvent } from './types'

afterEach(() => {
  vi.unstubAllGlobals()
})

function toReadableStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk))
      }
      controller.close()
    },
  })
}

async function collect(generator: AsyncGenerator<ChatEvent>): Promise<ChatEvent[]> {
  const events: ChatEvent[] = []
  for await (const event of generator) {
    events.push(event)
  }
  return events
}

function jsonResponse(body: unknown, init?: ResponseInit) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
}

describe('parseSse', () => {
  it('parses SSE when a frame is split across chunks', async () => {
    const chunks = [
      'event: data\ndata: {"kind":"matches","mat',
      'ches":[]}\n\nevent: text_delta\ndata: {"delta":"你好"}\n\n',
    ]
    const events = await collect(parseSse(toReadableStream(chunks)))
    expect(events).toEqual([
      { type: 'data', payload: { kind: 'matches', matches: [] } },
      { type: 'text_delta', payload: { delta: '你好' } },
    ])
  })

  it('parses a multibyte character split across chunks', async () => {
    const encoder = new TextEncoder()
    const full = encoder.encode('event: text_delta\ndata: {"delta":"澳门"}\n\n')
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(full.slice(0, 30))
        controller.enqueue(full.slice(30))
        controller.close()
      },
    })

    const events = await collect(parseSse(stream))
    expect(events).toEqual([{ type: 'text_delta', payload: { delta: '澳门' } }])
  })

  it('ignores comments and blank frames and joins repeated data lines', async () => {
    const chunks = [': heartbeat\n\n', 'event: done\ndata: {"ok"\ndata: :true}\n\n']
    const events = await collect(parseSse(toReadableStream(chunks)))
    expect(events).toEqual([{ type: 'done', payload: { ok: true } }])
  })

  it('handles CRLF frame boundaries', async () => {
    const chunks = ['event: status\r\ndata: {"stage":"resolving"}\r\n\r\n']
    const events = await collect(parseSse(toReadableStream(chunks)))
    expect(events).toEqual([{ type: 'status', payload: { stage: 'resolving' } }])
  })
})

describe('REST helpers', () => {
  it('unwraps the data envelope for player search', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ data: [{ id: 'ply_1', name: 'Jannik Sinner', country_code: 'ita', ranking: 1 }] }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const players = await getPlayers('Sinner')

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/players/search?q=Sinner',
      expect.objectContaining({ cache: 'no-store' }),
    )
    expect(players[0].id).toBe('ply_1')
  })

  it('builds match list query with optional player', async () => {
    const fetchMock = vi.fn().mockImplementation(async () => jsonResponse({ data: [] }))
    vi.stubGlobal('fetch', fetchMock)

    await getMatches('upcoming')
    await getMatches('live', 'Jannik Sinner')

    expect(fetchMock.mock.calls[0][0]).toBe('/api/matches?status=upcoming')
    expect(fetchMock.mock.calls[1][0]).toBe('/api/matches?status=live&player=Jannik+Sinner')
  })

  it('encodes the match id in the detail path', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ data: { id: 'mat_1' } }))
    vi.stubGlobal('fetch', fetchMock)

    await getMatch('mat_1/2')

    expect(fetchMock.mock.calls[0][0]).toBe('/api/matches/mat_1%2F2')
  })

  it('throws ApiError with code and details on non-2xx', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(
        {
          error: { code: 'ambiguous_player', message: 'Player name is ambiguous', details: { candidates: [] } },
          request_id: 'req-1',
        },
        { status: 409 },
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    const error = await getMatches('live', 'Sinner').catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(409)
    expect((error as ApiError).code).toBe('ambiguous_player')
    expect((error as ApiError).details).toEqual({ candidates: [] })
  })

  it('falls back to internal_error when the error body is unreadable', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('boom', { status: 503 }))
    vi.stubGlobal('fetch', fetchMock)

    const error = await getMatch('mat_1').catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(503)
    expect((error as ApiError).code).toBe('internal_error')
  })
})

describe('streamChat', () => {
  it('POSTs the request and yields parsed events', async () => {
    const stream = toReadableStream([
      'event: status\ndata: {"stage":"resolving"}\n\nevent: done\ndata: {"ok":true}\n\n',
    ])
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const events = await collect(
      streamChat({ scope: 'global', messages: [{ role: 'user', content: '今晚有比赛吗？' }] }),
    )

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/chat/stream')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toEqual({
      scope: 'global',
      messages: [{ role: 'user', content: '今晚有比赛吗？' }],
    })
    expect(events.map((event) => event.type)).toEqual(['status', 'done'])
  })

  it('throws ApiError before parsing on non-OK response', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(
        { error: { code: 'invalid_request', message: 'bad body', details: {} }, request_id: 'req-2' },
        { status: 422 },
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    const generator = streamChat({ scope: 'global', messages: [{ role: 'user', content: 'q' }] })

    await expect(collect(generator)).rejects.toMatchObject({ code: 'invalid_request', status: 422 })
  })

  it('propagates abort without turning it into internal_error', async () => {
    const abortError = new DOMException('The operation was aborted.', 'AbortError')
    const fetchMock = vi.fn().mockRejectedValue(abortError)
    vi.stubGlobal('fetch', fetchMock)

    const controller = new AbortController()
    controller.abort()

    const error = await collect(
      streamChat({ scope: 'global', messages: [{ role: 'user', content: 'q' }] }, controller.signal),
    ).catch((caught: unknown) => caught)

    expect(error).toBe(abortError)
    expect(error).not.toBeInstanceOf(ApiError)
  })
})
