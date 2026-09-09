import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MatchSnapshotDto } from '@/lib/api/types'
import { useMatchStream } from './use-match-stream'

type Script = {
  snapshotVersions: number[]
  frameSets: string[][]
  failStreamAfterFrames?: boolean
}

const script: Script = { snapshotVersions: [], frameSets: [] }
const snapshotCalls: string[] = []
const streamCalls: { url: string; signal?: AbortSignal }[] = []

function snapshotDto(version: number): MatchSnapshotDto {
  return {
    match: {
      id: 'mat_42',
      status: 'live',
      players: [
        { id: 'ply_1', name: 'Jannik Sinner', country_code: 'ita', ranking: 1 },
        { id: 'ply_2', name: 'Casper Ruud', country_code: 'nor', ranking: 4 },
      ],
      tournament: { id: 'trn_1', name: 'ATP Finals', tour: 'atp' },
      scheduled_at: '2026-09-08T10:00:00Z',
      round: 'Semifinal',
      surface: 'hard',
      indoor: true,
      format: 'BO3',
      live_state: { score: null, server_player_id: 'ply_1', state_version: version },
      winner_player_id: null,
      freshness: {
        provider: 'fake',
        source_updated_at: null,
        observed_at: '2026-09-08T10:00:00Z',
        is_stale: false,
        age_seconds: 0,
      },
    },
    points: [],
    statistics: [],
    momentum: [],
    quality: [],
    state_version: version,
    as_of: '2026-09-08T10:00:00Z',
  }
}

function frame(type: string, version: number, extra: Record<string, unknown> = {}) {
  const payload =
    type === 'ready'
      ? { snapshot: snapshotDto(version), state_version: version, as_of: 'x' }
      : type === 'match_delta'
        ? {
            match_id: 'mat_42',
            state_version: version,
            as_of: 'x',
            changes: ['point_appended'],
            snapshot: snapshotDto(version),
          }
        : type === 'match_ended'
          ? { match_id: 'mat_42', state_version: version, as_of: 'x' }
          : {}
  return `event: ${type}\n${type === 'heartbeat' ? '' : `id: ${version}\n`}data: ${JSON.stringify({
    ...payload,
    ...extra,
  })}\n\n`
}

function frameStream(frames: string[], signal: AbortSignal | undefined, fail: boolean) {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      const encoder = new TextEncoder()
      for (const chunk of frames) {
        if (signal?.aborted) return
        controller.enqueue(encoder.encode(chunk))
      }
      if (fail) {
        controller.error(new Error('stream boom'))
        return
      }
      // Real SSE streams stay open; mirror that and surface aborts as errors.
      signal?.addEventListener('abort', () => {
        try {
          controller.error(new DOMException('The operation was aborted.', 'AbortError'))
        } catch {
          /* already terminated */
        }
      })
    },
  })
}

beforeEach(() => {
  script.snapshotVersions = []
  script.frameSets = []
  script.failStreamAfterFrames = false
  snapshotCalls.length = 0
  streamCalls.length = 0
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      if (String(url).includes('/stream')) {
        streamCalls.push({ url: String(url), signal: init?.signal ?? undefined })
        const frames = script.frameSets.shift() ?? []
        return new Response(frameStream(frames, init?.signal ?? undefined, Boolean(script.failStreamAfterFrames)), {
          status: 200,
          headers: { 'content-type': 'text/event-stream' },
        })
      }
      snapshotCalls.push(String(url))
      const version = script.snapshotVersions.shift() ?? 1
      return Response.json({ data: snapshotDto(version) })
    }),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('useMatchStream', () => {
  it('loads the REST snapshot before opening the stream', async () => {
    script.snapshotVersions = [1]
    script.frameSets = [[frame('ready', 1)]]

    const { result } = renderHook(() => useMatchStream('mat_42'))

    await waitFor(() => expect(result.current.phase).toBe('live'))
    expect(snapshotCalls[0]).toBe('/api/matches/mat_42')
    expect(streamCalls).toHaveLength(1)
    expect(snapshotCalls).toHaveLength(1)
    expect(result.current.snapshot?.state_version).toBe(1)
  })

  it('applies consecutive deltas atomically', async () => {
    script.snapshotVersions = [1]
    script.frameSets = [[frame('ready', 1), frame('match_delta', 2), frame('match_delta', 3)]]

    const { result } = renderHook(() => useMatchStream('mat_42'))

    await waitFor(() => expect(result.current.snapshot?.state_version).toBe(3))
    expect(result.current.phase).not.toBe('error')
  })

  it('ignores duplicate versions without refetching', async () => {
    script.snapshotVersions = [2]
    script.frameSets = [[frame('ready', 2), frame('match_delta', 2), frame('match_delta', 2)]]

    const { result } = renderHook(() => useMatchStream('mat_42'))

    await waitFor(() => expect(result.current.phase).toBe('live'))
    await new Promise((resolve) => setTimeout(resolve, 100))
    expect(result.current.snapshot?.state_version).toBe(2)
    expect(snapshotCalls).toHaveLength(1)
  })

  it('refetches the snapshot when a version gap appears', async () => {
    script.snapshotVersions = [1, 5]
    script.frameSets = [[frame('ready', 1), frame('match_delta', 5)]]

    const { result } = renderHook(() => useMatchStream('mat_42'))

    await waitFor(() => expect(result.current.snapshot?.state_version).toBe(5))
    expect(snapshotCalls).toHaveLength(2)
  })

  it('ends the stream on match_ended without retrying', async () => {
    script.snapshotVersions = [1]
    script.frameSets = [[frame('ready', 1), frame('match_ended', 2)]]

    const { result } = renderHook(() => useMatchStream('mat_42'))

    await waitFor(() => expect(result.current.phase).toBe('ended'))
    await new Promise((resolve) => setTimeout(resolve, 2500))
    expect(streamCalls).toHaveLength(1)
  })

  it('keeps data and reconnects after a stream error', async () => {
    script.snapshotVersions = [1, 1]
    script.frameSets = [[frame('ready', 1)], [frame('ready', 1)]]
    script.failStreamAfterFrames = true

    const { result } = renderHook(() => useMatchStream('mat_42'))

    await waitFor(() => expect(result.current.phase).toBe('reconnecting'))
    expect(result.current.snapshot?.state_version).toBe(1)
    await waitFor(() => expect(streamCalls.length).toBeGreaterThanOrEqual(2), { timeout: 4000 })
  })

  it('releases the stream after 60s hidden and restores on visibility', async () => {
    vi.useFakeTimers()
    try {
      script.snapshotVersions = [1, 1]
      script.frameSets = [[frame('ready', 1)], [frame('ready', 1)]]

      const { result } = renderHook(() => useMatchStream('mat_42'))
      await act(async () => {
        await vi.advanceTimersByTimeAsync(50)
      })
      expect(result.current.phase).toBe('live')

      const hiddenSignal = streamCalls[0]?.signal
      Object.defineProperty(document, 'visibilityState', {
        configurable: true,
        value: 'hidden',
      })
      await act(async () => {
        document.dispatchEvent(new Event('visibilitychange'))
        await vi.advanceTimersByTimeAsync(60_000)
      })
      expect(result.current.phase).toBe('stale')
      expect(hiddenSignal?.aborted).toBe(true)

      script.failStreamAfterFrames = false
      Object.defineProperty(document, 'visibilityState', {
        configurable: true,
        value: 'visible',
      })
      await act(async () => {
        document.dispatchEvent(new Event('visibilitychange'))
        await vi.advanceTimersByTimeAsync(50)
      })
      expect(snapshotCalls.length).toBeGreaterThanOrEqual(2)
      expect(streamCalls.length).toBeGreaterThanOrEqual(2)
      expect(result.current.phase).toBe('live')
    } finally {
      vi.useRealTimers()
    }
  })

  it('aborts the stream on unmount', async () => {
    script.snapshotVersions = [1]
    script.frameSets = [[frame('ready', 1)]]

    const { result, unmount } = renderHook(() => useMatchStream('mat_42'))
    await waitFor(() => expect(result.current.phase).toBe('live'))
    const signal = streamCalls[0]?.signal

    unmount()

    expect(signal?.aborted).toBe(true)
  })
})
