// useDecisionStream contract tests (T67): REST snapshot first, its own
// observation_version cursor, version+1 deltas refetch the authoritative
// snapshot, duplicates ignored, gap/malformed keeps the last trusted view +
// degraded + refetches only decision state, reconnect carries its own
// Last-Event-ID, heartbeat timeout reconnects, and it never touches the
// useMatchStream (P2 sports) cursor or endpoints.
import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { DecisionSnapshotDto, MatchSnapshotDto } from '@/lib/api/types'
import { useDecisionStream } from './use-decision-stream'
import { useMatchStream } from './use-match-stream'

const NOW = '2026-09-16T12:00:00Z'

function decisionSnapshot(version: number, action: DecisionSnapshotDto['action'] = 'hold'): DecisionSnapshotDto {
  return {
    match_id: 'mat_9',
    market_id: 'mkt_9',
    action,
    reason_code: null,
    target_player_id: null,
    observation_version: version,
    model_probabilities: { ply_a: 0.55, ply_b: 0.45 },
    model_availability: 'available',
    quote_average_price: null,
    quote_side: null,
    conservative_net_edge: null,
    max_acceptable_price: null,
    hold_value: null,
    model_version: 'prematch-elo-v1',
    calibration_version: 'platt-v1',
    policy_version: 'policy-v1',
    data_version: 'apidata-v1',
    gates: [],
    outcome_levels: [],
    position: null,
    lifecycle: [],
    is_stale: false,
    has_gap: false,
    lock_profit_available: false,
    as_of: NOW,
  }
}

function frame(type: string, data: Record<string, unknown>, id?: string | null) {
  const idLine = id === undefined || id === null ? '' : `id: ${id}\n`
  return `event: ${type}\n${idLine}data: ${JSON.stringify(data)}\n\n`
}

function readyFrame(decision: DecisionSnapshotDto | null, version: number) {
  return frame(
    'ready',
    {
      match_id: 'mat_9',
      decision,
      observation_version: version,
      action: decision ? decision.action : null,
    },
    version > 0 ? String(version) : null,
  )
}

function deltaFrame(version: number, action = 'hold') {
  return frame(
    'decision_delta',
    { type: 'decision_delta', match_id: 'mat_9', observation_version: version, action, as_of: NOW },
    String(version),
  )
}

const script: {
  decisionVersions: number[] // REST snapshot versions served in order
  decisionStatuses: number[] // REST statuses (404 → null decision)
  failDecisionRest: boolean
  frameSets: string[][]
  failStreamAfterFrames: boolean
  stayOpen: boolean
} = {
  decisionVersions: [],
  decisionStatuses: [],
  failDecisionRest: false,
  frameSets: [],
  failStreamAfterFrames: false,
  stayOpen: false,
}
const restCalls: string[] = []
const streamCalls: { url: string; headers: Record<string, string>; signal?: AbortSignal }[] = []

function frameStream(frames: string[], signal: AbortSignal | undefined, fail: boolean, stayOpen: boolean) {
  const encoder = new TextEncoder()
  let index = 0
  return new ReadableStream<Uint8Array>({
    start(controller) {
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
      if (!stayOpen) {
        controller.close()
        return undefined
      }
      // Park the read: the stream stays open until aborted.
      return new Promise<void>(() => {})
    },
  })
}

beforeEach(() => {
  script.decisionVersions = []
  script.decisionStatuses = []
  script.failDecisionRest = false
  script.frameSets = []
  script.failStreamAfterFrames = false
  script.stayOpen = true
  restCalls.length = 0
  streamCalls.length = 0
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const target = String(url)
      if (target.includes('/decision/stream')) {
        streamCalls.push({
          url: target,
          headers: (init?.headers ?? {}) as Record<string, string>,
          signal: init?.signal ?? undefined,
        })
        const frames = script.frameSets.shift() ?? []
        return new Response(
          frameStream(frames, init?.signal ?? undefined, script.failStreamAfterFrames, script.stayOpen),
          { status: 200, headers: { 'content-type': 'text/event-stream' } },
        )
      }
      if (target.includes('/decision')) {
        restCalls.push(target)
        if (script.failDecisionRest) {
          return Response.json(
            { error: { code: 'internal_error', message: 'boom', details: {} } },
            { status: 500 },
          )
        }
        const status = script.decisionStatuses.shift() ?? 200
        if (status === 404) {
          return Response.json(
            { error: { code: 'not_found', message: 'No P3 decision context', details: {} } },
            { status: 404 },
          )
        }
        const version = script.decisionVersions.shift() ?? 1
        return Response.json({ data: decisionSnapshot(version) })
      }
      throw new Error(`unexpected fetch ${target}`)
    }),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('useDecisionStream', () => {
  it('loads the REST snapshot before opening its own stream', async () => {
    script.decisionVersions = [3]
    script.frameSets = [[readyFrame(decisionSnapshot(3), 3)]]

    const { result } = renderHook(() => useDecisionStream('mat_9'))

    await waitFor(() => expect(result.current.phase).toBe('live'))
    expect(restCalls[0]).toBe('/api/matches/mat_9/decision')
    expect(streamCalls[0].url).toBe('/api/matches/mat_9/decision/stream')
    expect(result.current.decision?.observation_version).toBe(3)
    expect(result.current.observationVersion).toBe(3)
    expect(result.current.degraded).toBe(false)
  })

  it('tolerates a 404 snapshot as an honest null decision', async () => {
    script.decisionStatuses = [404]
    script.frameSets = [[readyFrame(null, 0)]]

    const { result } = renderHook(() => useDecisionStream('mat_9'))

    await waitFor(() => expect(result.current.phase).toBe('live'))
    expect(result.current.decision).toBeNull()
    expect(result.current.observationVersion).toBe(0)
    expect(result.current.errorCode).toBeNull()
  })

  it('applies the ready snapshot when it is newer than the REST one', async () => {
    script.decisionVersions = [2]
    script.frameSets = [[readyFrame(decisionSnapshot(4, 'wait'), 4)]]

    const { result } = renderHook(() => useDecisionStream('mat_9'))

    await waitFor(() => expect(result.current.observationVersion).toBe(4))
    expect(result.current.decision?.action).toBe('wait')
  })

  it('ignores an older ready snapshot', async () => {
    script.decisionVersions = [6]
    script.frameSets = [[readyFrame(decisionSnapshot(4), 4)]]

    const { result } = renderHook(() => useDecisionStream('mat_9'))

    await waitFor(() => expect(result.current.phase).toBe('live'))
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50))
    })
    expect(result.current.observationVersion).toBe(6)
  })

  it('refetches the authoritative snapshot on a version+1 delta', async () => {
    script.decisionVersions = [3, 4]
    script.frameSets = [[readyFrame(decisionSnapshot(3), 3), deltaFrame(4, 'buy')]]

    const { result } = renderHook(() => useDecisionStream('mat_9'))

    await waitFor(() => expect(result.current.observationVersion).toBe(4))
    expect(result.current.decision?.action).toBe('hold') // REST snapshot is authority
    expect(restCalls).toHaveLength(2)
    expect(result.current.degraded).toBe(false)
  })

  it('ignores duplicate and stale deltas without refetching', async () => {
    script.decisionVersions = [3]
    script.frameSets = [[readyFrame(decisionSnapshot(3), 3), deltaFrame(3), deltaFrame(2), deltaFrame(3)]]

    const { result } = renderHook(() => useDecisionStream('mat_9'))

    await waitFor(() => expect(result.current.phase).toBe('live'))
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50))
    })
    expect(result.current.observationVersion).toBe(3)
    expect(restCalls).toHaveLength(1) // only the initial snapshot load
  })

  it('keeps the last trusted view on a gap, degrades and refetches only the decision', async () => {
    script.decisionVersions = [3, 9]
    script.frameSets = [[readyFrame(decisionSnapshot(3), 3), deltaFrame(9, 'buy')]]

    const { result } = renderHook(() => useDecisionStream('mat_9'))

    await waitFor(() => expect(result.current.observationVersion).toBe(9))
    expect(result.current.decision?.observation_version).toBe(9)
    expect(restCalls).toHaveLength(2) // gap refetched decision state only
    expect(result.current.degraded).toBe(false) // recovered via refetch
  })

  it('stays on the last trusted view and remains degraded when the gap refetch fails', async () => {
    script.decisionVersions = [3]
    script.frameSets = [[readyFrame(decisionSnapshot(3), 3), deltaFrame(9)]]

    const { result } = renderHook(() => useDecisionStream('mat_9'))
    await waitFor(() => expect(result.current.observationVersion).toBe(3))

    script.failDecisionRest = true
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 10))
    })
    // The gap delta arrives while REST is failing.
    await waitFor(() => expect(result.current.degraded).toBe(true), { timeout: 2000 })
    expect(result.current.decision?.observation_version).toBe(3) // last trusted kept
    expect(result.current.observationVersion).toBe(3)
  })

  it('treats a malformed delta like a gap: keep, degrade, refetch', async () => {
    script.decisionVersions = [3, 3]
    script.frameSets = [
      [
        readyFrame(decisionSnapshot(3), 3),
        frame('decision_delta', { match_id: 'mat_9', observation_version: 'x', action: 'buy' }, '4'),
      ],
    ]

    const { result } = renderHook(() => useDecisionStream('mat_9'))

    await waitFor(() => expect(restCalls.length).toBe(2))
    expect(result.current.degraded).toBe(true) // refetch could not advance past 3
    expect(result.current.decision?.observation_version).toBe(3)
  })

  it('reconnects after a stream error carrying its own Last-Event-ID', async () => {
    script.decisionVersions = [3, 3]
    script.frameSets = [[readyFrame(decisionSnapshot(3), 3)], [readyFrame(decisionSnapshot(3), 3)]]
    script.failStreamAfterFrames = true

    const { result } = renderHook(() => useDecisionStream('mat_9'))

    await waitFor(() => expect(result.current.phase).toBe('reconnecting'))
    script.failStreamAfterFrames = false
    await waitFor(() => expect(streamCalls.length).toBeGreaterThanOrEqual(2), { timeout: 4000 })
    expect(streamCalls[1].headers['Last-Event-ID']).toBe('3')
    await waitFor(() => expect(result.current.phase).toBe('live'))
  })

  it('reconnects when heartbeats stop arriving', async () => {
    vi.useFakeTimers()
    try {
      script.decisionVersions = [3, 3]
      script.frameSets = [[readyFrame(decisionSnapshot(3), 3)], [readyFrame(decisionSnapshot(3), 3)]]

      const { result } = renderHook(() => useDecisionStream('mat_9'))
      await act(async () => {
        await vi.advanceTimersByTimeAsync(50)
      })
      expect(result.current.phase).toBe('live')

      await act(async () => {
        await vi.advanceTimersByTimeAsync(46_000)
      })
      expect(streamCalls[0].signal?.aborted).toBe(true)
      await act(async () => {
        await vi.advanceTimersByTimeAsync(2_100)
      })
      expect(streamCalls.length).toBeGreaterThanOrEqual(2)
    } finally {
      vi.useRealTimers()
    }
  })

  it('aborts the stream on unmount', async () => {
    script.decisionVersions = [3]
    script.frameSets = [[readyFrame(decisionSnapshot(3), 3)]]

    const { result, unmount } = renderHook(() => useDecisionStream('mat_9'))
    await waitFor(() => expect(result.current.phase).toBe('live'))
    const signal = streamCalls[0]?.signal

    unmount()

    expect(signal?.aborted).toBe(true)
  })

  it('never changes the useMatchStream cursor or endpoints', async () => {
    // Combined harness: both hooks run against one routed fetch mock.
    vi.unstubAllGlobals()
    const matchRestCalls: string[] = []
    const matchStreamCalls: { url: string; headers: Record<string, string> }[] = []
    const matchSnapshot = (version: number): MatchSnapshotDto => ({
      match: {
        id: 'mat_9',
        status: 'live',
        players: [
          { id: 'ply_1', name: 'A', country_code: null, ranking: null },
          { id: 'ply_2', name: 'B', country_code: null, ranking: null },
        ],
        tournament: { id: 'trn', name: 'T', tour: null },
        scheduled_at: null,
        round: null,
        surface: null,
        indoor: null,
        format: null,
        live_state: { score: null, server_player_id: null, state_version: version },
        winner_player_id: null,
        freshness: {
          provider: 'fake',
          source_updated_at: null,
          observed_at: NOW,
          is_stale: false,
          age_seconds: 0,
        },
      },
      points: [],
      statistics: [],
      momentum: [],
      quality: [],
      state_version: version,
      as_of: NOW,
    })
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        const target = String(url)
        if (target.includes('/decision/stream')) {
          streamCalls.push({ url: target, headers: (init?.headers ?? {}) as Record<string, string>, signal: init?.signal ?? undefined })
          const frames = script.frameSets.shift() ?? []
          return new Response(frameStream(frames, init?.signal ?? undefined, false, true), {
            status: 200,
            headers: { 'content-type': 'text/event-stream' },
          })
        }
        if (target.includes('/decision')) {
          restCalls.push(target)
          const version = script.decisionVersions.shift() ?? 1
          return Response.json({ data: decisionSnapshot(version) })
        }
        if (target.endsWith('/stream')) {
          matchStreamCalls.push({ url: target, headers: (init?.headers ?? {}) as Record<string, string> })
          const sports = [
            frame('ready', { snapshot: matchSnapshot(11), state_version: 11, as_of: NOW }, '11'),
          ]
          return new Response(frameStream(sports, init?.signal ?? undefined, false, true), {
            status: 200,
            headers: { 'content-type': 'text/event-stream' },
          })
        }
        matchRestCalls.push(target)
        return Response.json({ data: matchSnapshot(11) })
      }),
    )
    script.decisionVersions = [3, 4]
    script.frameSets = [[readyFrame(decisionSnapshot(3), 3), deltaFrame(4, 'buy')]]

    const { result } = renderHook(() => {
      const match = useMatchStream('mat_9')
      const decision = useDecisionStream('mat_9')
      return { match, decision }
    })

    await waitFor(() => expect(result.current.decision.observationVersion).toBe(4))
    await waitFor(() => expect(result.current.match.phase).toBe('live'))
    // The P2 sports view and cursor are untouched by decision traffic.
    expect(result.current.match.snapshot?.state_version).toBe(11)
    expect(matchRestCalls).toEqual(['/api/matches/mat_9'])
    expect(matchStreamCalls).toHaveLength(1)
    expect(matchStreamCalls[0].url).toBe('/api/matches/mat_9/stream')
    // Decision traffic only ever hit decision endpoints.
    expect(restCalls.every((url) => url.includes('/decision'))).toBe(true)
    expect(streamCalls.every((call) => call.url.includes('/decision/stream'))).toBe(true)
  })
})
