// P3 markets stream hook (T67). Snapshot-first: the ready frame carries the
// authoritative counters; per-resource cursors (market sequence, decision
// observation_version) apply only contiguous advances, ignore duplicates and
// stale events, and on a gap keep the last trusted view, mark it degraded and
// signal a resource refetch. Malformed deltas never kill the stream. A final
// resolution freezes its market. Reconnect carries this stream's own last
// event ID and never touches the P2 match stream.
import { useCallback, useEffect, useRef, useState } from 'react'

import { openMarketStream, parseMarketStream, type MarketStreamFrame } from '@/lib/api/client'
import type {
  MarketsSnapshotDto,
  QuoteCatalogChangedDto,
  ResolutionStatusValue,
} from '@/lib/api/types'

const RETRY_MS = 2_000
// Three times the backend default heartbeat interval (15s).
const HEARTBEAT_TIMEOUT_MS = 45_000
const GAP_LOG_LIMIT = 20

export type MarketStreamGap = { kind: 'market' | 'decision' | 'malformed'; id: string | null }
export type MarketStreamPhase = 'loading' | 'live' | 'reconnecting' | 'error'

export type MarketBookView = {
  market_id: string
  sequence: number
  book_hash: string
  as_of: string
}
export type MarketDecisionView = {
  match_id: string
  observation_version: number
  action: string
  as_of: string
}
export type MarketPaperView = {
  state: string
  id: string
  reason: string | null
  as_of: string
}
export type MarketResolutionView = {
  market_id: string
  status: ResolutionStatusValue
  confirmed_at?: string | null
}

type ViewState = {
  snapshot: MarketsSnapshotDto | null
  books: Record<string, MarketBookView>
  decisions: Record<string, MarketDecisionView>
  paper: Record<string, MarketPaperView>
  resolutions: Record<string, MarketResolutionView>
  gaps: MarketStreamGap[]
}

const EMPTY_VIEW: ViewState = {
  snapshot: null,
  books: {},
  decisions: {},
  paper: {},
  resolutions: {},
  gaps: [],
}

export type MarketStreamState = ViewState & {
  phase: MarketStreamPhase
  errorCode: string | null
  lastEventId: string | null
  refresh: () => Promise<void>
}

function errorCodeOf(error: unknown): string {
  return typeof error === 'object' && error !== null && 'code' in error
    ? String((error as { code: unknown }).code)
    : 'internal_error'
}

function isAbort(error: unknown): boolean {
  return (
    (error instanceof DOMException && error.name === 'AbortError') ||
    (error instanceof Error && error.name === 'AbortError')
  )
}

export function useMarketStream(
  options: {
    onGap?: (gap: MarketStreamGap) => void
    onQuotesChanged?: (event: QuoteCatalogChangedDto) => void
  } = {},
): MarketStreamState {
  const [view, setView] = useState<ViewState>(EMPTY_VIEW)
  const [phase, setPhase] = useState<MarketStreamPhase>('loading')
  const [errorCode, setErrorCode] = useState<string | null>(null)
  const [lastEventId, setLastEventId] = useState<string | null>(null)

  const cursorsRef = useRef<{
    markets: Record<string, number>
    decisions: Record<string, number>
  }>({ markets: {}, decisions: {} })
  const resolvedRef = useRef<Set<string>>(new Set())
  const quoteCatalogSequenceRef = useRef(0)
  const lastEventIdRef = useRef<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const retryRef = useRef<number | null>(null)
  const watchdogRef = useRef<number | null>(null)
  const hasSnapshotRef = useRef(false)
  const onGapRef = useRef(options.onGap)
  onGapRef.current = options.onGap
  const onQuotesChangedRef = useRef(options.onQuotesChanged)
  onQuotesChangedRef.current = options.onQuotesChanged
  const openStreamRef = useRef<() => Promise<void>>(async () => {})

  const recordGap = useCallback((gap: MarketStreamGap) => {
    setView((current) => ({
      ...current,
      gaps: [...current.gaps, gap].slice(-GAP_LOG_LIMIT),
    }))
    onGapRef.current?.(gap)
  }, [])

  const applyFrame = useCallback(
    (frame: MarketStreamFrame) => {
      if (frame.id !== null) {
        lastEventIdRef.current = frame.id
        setLastEventId(frame.id)
      }
      switch (frame.type) {
        case 'ready': {
          // The ready snapshot is authoritative: rebaseline every cursor so
          // the next delta per resource starts a fresh trusted sequence.
          hasSnapshotRef.current = true
          cursorsRef.current = { markets: {}, decisions: {} }
          quoteCatalogSequenceRef.current = 0
          resolvedRef.current = new Set()
          setView((current) => ({ ...current, snapshot: frame.payload }))
          return
        }
        case 'quotes_changed': {
          if (frame.payload.sequence <= quoteCatalogSequenceRef.current) return
          quoteCatalogSequenceRef.current = frame.payload.sequence
          onQuotesChangedRef.current?.(frame.payload)
          return
        }
        case 'market_delta': {
          const { market_id: marketId, sequence } = frame.payload
          if (resolvedRef.current.has(marketId)) return // terminal: frozen
          const cursor = cursorsRef.current.markets[marketId]
          if (cursor === undefined) {
            cursorsRef.current.markets[marketId] = sequence
            setView((current) => ({
              ...current,
              books: { ...current.books, [marketId]: { ...frame.payload } },
            }))
            return
          }
          if (sequence <= cursor) return // duplicate or stale
          if (sequence === cursor + 1) {
            cursorsRef.current.markets[marketId] = sequence
            setView((current) => ({
              ...current,
              books: { ...current.books, [marketId]: { ...frame.payload } },
            }))
            return
          }
          // Gap: keep the last trusted view, mark degraded, let the consumer
          // refetch the market resource; rebaseline so streaming can resume.
          cursorsRef.current.markets[marketId] = sequence
          recordGap({ kind: 'market', id: marketId })
          return
        }
        case 'decision_delta': {
          const { match_id: matchId, observation_version: version } = frame.payload
          const cursor = cursorsRef.current.decisions[matchId]
          if (cursor === undefined) {
            cursorsRef.current.decisions[matchId] = version
            setView((current) => ({
              ...current,
              decisions: { ...current.decisions, [matchId]: { ...frame.payload } },
            }))
            return
          }
          if (version <= cursor) return
          if (version === cursor + 1) {
            cursorsRef.current.decisions[matchId] = version
            setView((current) => ({
              ...current,
              decisions: { ...current.decisions, [matchId]: { ...frame.payload } },
            }))
            return
          }
          cursorsRef.current.decisions[matchId] = version
          recordGap({ kind: 'decision', id: matchId })
          return
        }
        case 'market_gap': {
          // Backend overlay: the hot book stayed as the last trusted view.
          recordGap({ kind: 'market', id: frame.payload.market_id })
          return
        }
        case 'paper_delta': {
          const { id, state, reason, as_of: asOf } = frame.payload
          setView((current) => ({
            ...current,
            paper: { ...current.paper, [id]: { id, state, reason, as_of: asOf } },
          }))
          return
        }
        case 'resolution_delta': {
          const { market_id: marketId, status, confirmed_at: confirmedAt } = frame.payload
          if (status === 'final') resolvedRef.current.add(marketId)
          setView((current) => ({
            ...current,
            resolutions: {
              ...current.resolutions,
              [marketId]: { market_id: marketId, status, confirmed_at: confirmedAt },
            },
          }))
          return
        }
        case 'malformed':
          recordGap({ kind: 'malformed', id: null })
          return
        case 'heartbeat':
          return
      }
    },
    [recordGap],
  )

  const scheduleRetry = useCallback(() => {
    if (retryRef.current !== null) return
    retryRef.current = window.setTimeout(() => {
      retryRef.current = null
      void openStreamRef.current()
    }, RETRY_MS)
  }, [])

  const resetWatchdog = useCallback(
    (controller: AbortController) => {
      if (watchdogRef.current !== null) window.clearTimeout(watchdogRef.current)
      watchdogRef.current = window.setTimeout(() => {
        watchdogRef.current = null
        controller.abort()
        setPhase(hasSnapshotRef.current ? 'reconnecting' : 'loading')
        scheduleRetry()
      }, HEARTBEAT_TIMEOUT_MS)
    },
    [scheduleRetry],
  )

  const openStream = useCallback(async () => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    try {
      const response = await openMarketStream({
        signal: controller.signal,
        lastEventId: lastEventIdRef.current,
      })
      if (controller.signal.aborted) return
      setPhase('live')
      setErrorCode(null)
      resetWatchdog(controller)
      for await (const frame of parseMarketStream(response.body as ReadableStream<Uint8Array>)) {
        if (controller.signal.aborted) return
        resetWatchdog(controller)
        applyFrame(frame)
      }
      if (!controller.signal.aborted) {
        setPhase(hasSnapshotRef.current ? 'reconnecting' : 'loading')
        scheduleRetry()
      }
    } catch (error) {
      if (isAbort(error) || controller.signal.aborted) return
      if (hasSnapshotRef.current) {
        setPhase('reconnecting')
        scheduleRetry()
      } else {
        setErrorCode(errorCodeOf(error))
        setPhase('error')
      }
    }
  }, [applyFrame, resetWatchdog, scheduleRetry])

  openStreamRef.current = openStream

  const refresh = useCallback(async () => {
    if (retryRef.current !== null) {
      window.clearTimeout(retryRef.current)
      retryRef.current = null
    }
    setPhase('loading')
    await openStream()
  }, [openStream])

  useEffect(() => {
    void openStream()
    return () => {
      if (retryRef.current !== null) {
        window.clearTimeout(retryRef.current)
        retryRef.current = null
      }
      if (watchdogRef.current !== null) {
        window.clearTimeout(watchdogRef.current)
        watchdogRef.current = null
      }
      abortRef.current?.abort()
    }
  }, [openStream])

  return { ...view, phase, errorCode, lastEventId, refresh }
}
