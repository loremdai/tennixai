// useMarketStream contract tests (T67): snapshot-first ready, per-resource
// cursors (market sequence / decision observation_version), duplicate and
// stale events ignored, gap keeps the last trusted view + marks degraded +
// signals a resource refetch, malformed deltas never kill the stream,
// terminal resolution freezes a market, reconnect carries the stream's own
// last event ID, unmount aborts.
import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useMarketStream, type MarketStreamGap } from './use-market-stream'

const NOW = '2026-09-16T12:00:00Z'

const script: {
  frameSets: string[][]
  failStreamAfterFrames: boolean
} = { frameSets: [], failStreamAfterFrames: false }
const streamCalls: { url: string; headers: Record<string, string>; signal?: AbortSignal }[] = []
const gaps: MarketStreamGap[] = []

function frame(type: string, data: Record<string, unknown>, id?: string | null) {
  const idLine = id === undefined || id === null ? '' : `id: ${id}\n`
  return `event: ${type}\n${idLine}data: ${JSON.stringify(data)}\n\n`
}

function readyFrame(markets = 2, opportunities = 1, openPositions = 0) {
  return frame('ready', { markets, opportunities, open_positions: openPositions })
}

function marketDelta(marketId: string, sequence: number, bookHash = `h${sequence}`) {
  return frame(
    'market_delta',
    { type: 'market_delta', market_id: marketId, sequence, book_hash: bookHash, as_of: NOW },
    String(sequence),
  )
}

function decisionDelta(matchId: string, version: number, action = 'wait') {
  return frame(
    'decision_delta',
    { type: 'decision_delta', match_id: matchId, observation_version: version, action, as_of: NOW },
    String(version),
  )
}

function frameStream(frames: string[], signal: AbortSignal | undefined, fail: boolean) {
  const encoder = new TextEncoder()
  let index = 0
  return new ReadableStream<Uint8Array>({
    start(controller) {
      // Real SSE streams stay open; surface aborts as errors.
      signal?.addEventListener('abort', () => {
        try {
          controller.error(new DOMException('The operation was aborted.', 'AbortError'))
        } catch {
          /* already terminated */
        }
      })
    },
    pull(controller) {
      if (signal?.aborted) return undefined
      if (index < frames.length) {
        controller.enqueue(encoder.encode(frames[index++]))
        return undefined
      }
      if (fail) {
        controller.error(new Error('stream boom'))
        return undefined
      }
      // Park the read: the stream stays open until aborted.
      return new Promise<void>(() => {})
    },
  })
}

beforeEach(() => {
  script.frameSets = []
  script.failStreamAfterFrames = false
  streamCalls.length = 0
  gaps.length = 0
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      streamCalls.push({
        url: String(url),
        headers: (init?.headers ?? {}) as Record<string, string>,
        signal: init?.signal ?? undefined,
      })
      const frames = script.frameSets.shift() ?? []
      return new Response(
        frameStream(frames, init?.signal ?? undefined, script.failStreamAfterFrames),
        { status: 200, headers: { 'content-type': 'text/event-stream' } },
      )
    }),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('useMarketStream', () => {
  it('applies the ready snapshot first', async () => {
    script.frameSets = [[readyFrame(3, 2, 1)]]

    const { result } = renderHook(() => useMarketStream({ onGap: (gap) => gaps.push(gap) }))

    await waitFor(() => expect(result.current.phase).toBe('live'))
    expect(result.current.snapshot).toEqual({
      markets: 3,
      opportunities: 2,
      open_positions: 1,
      availability: null,
    })
    expect(streamCalls[0].url).toBe('/api/markets/stream')
  })

  it('applies ordered deltas per resource cursor', async () => {
    script.frameSets = [[readyFrame(), marketDelta('mkt_1', 12), marketDelta('mkt_1', 13), decisionDelta('mat_1', 5), decisionDelta('mat_1', 6, 'buy')]]

    const { result } = renderHook(() => useMarketStream({ onGap: (gap) => gaps.push(gap) }))

    await waitFor(() => expect(result.current.decisions['mat_1']?.observation_version).toBe(6))
    expect(result.current.books['mkt_1']?.sequence).toBe(13)
    expect(result.current.decisions['mat_1']?.action).toBe('buy')
    expect(gaps).toEqual([])
  })

  it('ignores duplicate and stale events without marking gaps', async () => {
    script.frameSets = [[readyFrame(), marketDelta('mkt_1', 12), marketDelta('mkt_1', 12), marketDelta('mkt_1', 11), decisionDelta('mat_1', 5), decisionDelta('mat_1', 5), decisionDelta('mat_1', 3)]]

    const { result } = renderHook(() => useMarketStream({ onGap: (gap) => gaps.push(gap) }))

    await waitFor(() => expect(result.current.books['mkt_1']?.sequence).toBe(12))
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50))
    })
    expect(result.current.decisions['mat_1']?.observation_version).toBe(5)
    expect(gaps).toEqual([])
  })

  it('keeps the last trusted view on a gap and signals the resource refetch', async () => {
    script.frameSets = [[readyFrame(), marketDelta('mkt_1', 12), marketDelta('mkt_1', 16)]]

    const { result } = renderHook(() => useMarketStream({ onGap: (gap) => gaps.push(gap) }))

    await waitFor(() => expect(gaps.length).toBe(1))
    expect(gaps[0]).toMatchObject({ kind: 'market', id: 'mkt_1' })
    // The gapped jump is never applied; the trusted view stays at 12.
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50))
    })
    expect(result.current.books['mkt_1']?.sequence).toBe(12)
  })

  it('rebaselines after a gap so contiguous deltas apply again', async () => {
    script.frameSets = [[readyFrame(), marketDelta('mkt_1', 12), marketDelta('mkt_1', 16), marketDelta('mkt_1', 17)]]

    const { result } = renderHook(() => useMarketStream({ onGap: (gap) => gaps.push(gap) }))

    await waitFor(() => expect(result.current.books['mkt_1']?.sequence).toBe(17))
    // Exactly one gap: the jump to 16. The rebaselined 17 applies cleanly.
    expect(gaps).toHaveLength(1)
    expect(gaps[0]).toMatchObject({ kind: 'market', id: 'mkt_1' })
  })

  it('marks decision gaps per match without touching other matches', async () => {
    script.frameSets = [[readyFrame(), decisionDelta('mat_1', 5), decisionDelta('mat_2', 5), decisionDelta('mat_1', 9)]]

    const { result } = renderHook(() => useMarketStream({ onGap: (gap) => gaps.push(gap) }))

    await waitFor(() => expect(gaps.length).toBe(1))
    expect(gaps[0]).toMatchObject({ kind: 'decision', id: 'mat_1' })
    expect(result.current.decisions['mat_1']?.observation_version).toBe(5)
    expect(result.current.decisions['mat_2']?.observation_version).toBe(5)
  })

  it('survives malformed deltas and keeps streaming', async () => {
    script.frameSets = [
      [
        readyFrame(),
        marketDelta('mkt_1', 12),
        frame('market_delta', { market_id: 'mkt_1' }, '13'), // missing sequence
        frame('odds_delta', { market_id: 'mkt_1' }, '14'), // unknown discriminator
        marketDelta('mkt_1', 13),
      ],
    ]

    const { result } = renderHook(() => useMarketStream({ onGap: (gap) => gaps.push(gap) }))

    await waitFor(() => expect(result.current.books['mkt_1']?.sequence).toBe(13))
    expect(gaps.filter((gap) => gap.kind === 'malformed').length).toBeGreaterThanOrEqual(1)
    expect(result.current.phase).toBe('live')
  })

  it('freezes a market after a terminal final resolution', async () => {
    script.frameSets = [
      [
        readyFrame(),
        marketDelta('mkt_1', 12),
        frame(
          'resolution_delta',
          {
            type: 'resolution_delta',
            market_id: 'mkt_1',
            status: 'final',
            rules_version: 1,
            payouts: [
              { player_id: 'ply_a', payout_per_share: '1' },
              { player_id: 'ply_b', payout_per_share: '0' },
            ],
            confirmed_at: NOW,
          },
          '13',
        ),
        marketDelta('mkt_1', 14),
      ],
    ]

    const { result } = renderHook(() => useMarketStream({ onGap: (gap) => gaps.push(gap) }))

    await waitFor(() => expect(result.current.resolutions['mkt_1']?.status).toBe('final'))
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50))
    })
    expect(result.current.books['mkt_1']?.sequence).toBe(12) // frozen, no gap noise
    expect(gaps).toEqual([])
  })

  it('records paper lifecycle deltas', async () => {
    script.frameSets = [
      [readyFrame(), frame('paper_delta', { type: 'paper_delta', state: 'filled', id: 'mat_1', reason: null, as_of: NOW }, '1')],
    ]

    const { result } = renderHook(() => useMarketStream({ onGap: (gap) => gaps.push(gap) }))

    await waitFor(() => expect(result.current.paper['mat_1']?.state).toBe('filled'))
  })

  it('reconnects after a stream error carrying its own last event ID', async () => {
    script.frameSets = [[readyFrame(), marketDelta('mkt_1', 12)], [readyFrame()]]
    script.failStreamAfterFrames = true

    const { result } = renderHook(() => useMarketStream({ onGap: (gap) => gaps.push(gap) }))

    await waitFor(() => expect(result.current.phase).toBe('reconnecting'))
    script.failStreamAfterFrames = false
    await waitFor(() => expect(streamCalls.length).toBeGreaterThanOrEqual(2), { timeout: 4000 })
    expect(streamCalls[1].headers['Last-Event-ID']).toBe('12')
    await waitFor(() => expect(result.current.phase).toBe('live'))
  })

  it('rebaselines cursors after a reconnect ready frame', async () => {
    script.frameSets = [[readyFrame(), marketDelta('mkt_1', 12)], [readyFrame(4, 1, 0), marketDelta('mkt_1', 99)]]
    script.failStreamAfterFrames = true

    const { result } = renderHook(() => useMarketStream({ onGap: (gap) => gaps.push(gap) }))

    await waitFor(() => expect(result.current.phase).toBe('reconnecting'))
    script.failStreamAfterFrames = false
    await waitFor(() => expect(result.current.snapshot?.markets).toBe(4), { timeout: 4000 })
    await waitFor(() => expect(result.current.books['mkt_1']?.sequence).toBe(99))
    expect(gaps).toEqual([])
  })

  it('aborts the stream on unmount', async () => {
    script.frameSets = [[readyFrame()]]

    const { result, unmount } = renderHook(() => useMarketStream())
    await waitFor(() => expect(result.current.phase).toBe('live'))
    const signal = streamCalls[0]?.signal

    unmount()

    expect(signal?.aborted).toBe(true)
  })
})
