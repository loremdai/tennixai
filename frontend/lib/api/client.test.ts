// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  ApiError,
  getMatchCatalog,
  getMatches,
  getMatchSnapshot,
  getPlayerProfile,
  getPlayerRankings,
  getPlayerResults,
  getPlayers,
  parseSse,
  searchPlayerDirectory,
  streamChat,
} from './client'
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

    await getMatchSnapshot('mat_1/2')

    expect(fetchMock.mock.calls[0][0]).toBe('/api/matches/mat_1%2F2')
  })

  it('builds catalog queries with repeated facet params and expands empty groups to all', async () => {
    const fetchMock = vi.fn().mockImplementation(async () =>
      jsonResponse({
        data: {
          status: 'upcoming',
          matches: [],
          filters: { circuits: [], genders: [], disciplines: [] },
          facet_counts: {
            circuits: { atp: 0, wta: 0, challenger: 0, itf: 0, other: 0 },
            genders: { men: 0, women: 0, mixed: 0, unknown: 0 },
            disciplines: { singles: 0, doubles: 0, team: 0, unknown: 0 },
          },
          featured_match_id: null,
        },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await getMatchCatalog('upcoming', {
      circuits: ['atp', 'wta'],
      genders: [],
      disciplines: ['singles'],
    })
    await getMatchCatalog('live', {
      circuits: ['itf'],
      genders: ['women'],
      disciplines: ['doubles'],
    })

    expect(fetchMock.mock.calls[0][0]).toBe(
      '/api/matches/catalog?status=upcoming&circuit=atp&circuit=wta&gender=men&gender=women&gender=mixed&gender=unknown&discipline=singles',
    )
    expect(fetchMock.mock.calls[1][0]).toBe(
      '/api/matches/catalog?status=live&circuit=itf&gender=women&discipline=doubles',
    )
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

    const error = await getMatchSnapshot('mat_1').catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(503)
    expect((error as ApiError).code).toBe('internal_error')
  })
})

describe('P2.6 player directory clients', () => {
  it('forwards rankings tour, page and optional country verbatim', async () => {
    const fetchMock = vi.fn().mockImplementation(async () => jsonResponse({ data: {} }))
    vi.stubGlobal('fetch', fetchMock)

    await getPlayerRankings({ tour: 'WTA', page: 2, country: 'CHN' })
    await getPlayerRankings({ tour: 'ATP', page: 1 })

    expect(fetchMock.mock.calls[0][0]).toBe('/api/players/rankings?tour=WTA&page=2&country=CHN')
    expect(fetchMock.mock.calls[1][0]).toBe('/api/players/rankings?tour=ATP&page=1')
  })

  it('forwards the encoded directory search query and limit', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ data: { status: 'not_found', query: '谢尔顿', player: null, candidates: [] } }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const resolution = await searchPlayerDirectory('谢尔顿', 20)

    expect(fetchMock.mock.calls[0][0]).toBe(
      `/api/players/search?q=${encodeURIComponent('谢尔顿')}&limit=20`,
    )
    expect(resolution.status).toBe('not_found')
  })

  it('encodes the player id and appends the optional season for profiles', async () => {
    const fetchMock = vi.fn().mockImplementation(async () => jsonResponse({ data: {} }))
    vi.stubGlobal('fetch', fetchMock)

    await getPlayerProfile('ply_1/2')
    await getPlayerProfile('ply_1', 2025)

    expect(fetchMock.mock.calls[0][0]).toBe('/api/players/ply_1%2F2')
    expect(fetchMock.mock.calls[1][0]).toBe('/api/players/ply_1?season=2025')
  })

  it('repeats tier params and forwards outcome, season and page for results', async () => {
    const fetchMock = vi.fn().mockImplementation(async () => jsonResponse({ data: {} }))
    vi.stubGlobal('fetch', fetchMock)

    await getPlayerResults('ply_1/2', {
      season: 2026,
      tiers: ['atp', 'itf'],
      outcome: 'won',
      page: 3,
    })

    expect(fetchMock.mock.calls[0][0]).toBe(
      '/api/players/ply_1%2F2/results?season=2026&page=3&tier=atp&tier=itf&outcome=won',
    )
  })

  it('maps backend player failures onto ApiError', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(
        { error: { code: 'not_found', message: 'Player not found', details: {} } },
        { status: 404 },
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    const error = await getPlayerProfile('ply_missing').catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(404)
    expect((error as ApiError).code).toBe('not_found')
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
