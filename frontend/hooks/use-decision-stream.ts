// P3 decision stream hook (T67). Snapshot-first from the authoritative REST
// decision snapshot; the stream's own observation_version cursor applies only
// contiguous advances (a version+1 delta refetches the full snapshot — deltas
// are signals, PostgreSQL stays the authority). Duplicates/stale events are
// ignored. A gap or malformed delta keeps the last trusted view, marks the
// hook degraded and refetches only decision state. Reconnect carries this
// stream's own Last-Event-ID and never touches the P2 match stream cursor.
import { useCallback, useEffect, useRef, useState } from 'react'

import {
  ApiError,
  getMatchDecision,
  openDecisionStream,
  parseDecisionStream,
  type DecisionStreamFrame,
} from '@/lib/api/client'
import type { DecisionSnapshotDto } from '@/lib/api/types'

const RETRY_MS = 2_000
// Three times the backend default heartbeat interval (15s).
const HEARTBEAT_TIMEOUT_MS = 45_000

export type DecisionStreamPhase = 'loading' | 'live' | 'reconnecting' | 'error'

export type DecisionStreamState = {
  decision: DecisionSnapshotDto | null
  observationVersion: number
  phase: DecisionStreamPhase
  degraded: boolean
  errorCode: string | null
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

export function useDecisionStream(matchId: string | undefined): DecisionStreamState {
  const [decision, setDecision] = useState<DecisionSnapshotDto | null>(null)
  const [observationVersion, setObservationVersion] = useState(0)
  const [phase, setPhase] = useState<DecisionStreamPhase>('loading')
  const [degraded, setDegraded] = useState(false)
  const [errorCode, setErrorCode] = useState<string | null>(null)

  const cursorRef = useRef(0)
  const loadedRef = useRef(false)
  const lastEventIdRef = useRef<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const retryRef = useRef<number | null>(null)
  const watchdogRef = useRef<number | null>(null)
  const openStreamRef = useRef<() => Promise<void>>(async () => {})

  const fetchDecision = useCallback(
    async (
      target: number,
      opts: { initial: boolean; signal?: AbortSignal },
    ): Promise<boolean> => {
      if (!matchId) return false
      try {
        const fresh = await getMatchDecision(matchId, opts.signal)
        if (opts.signal?.aborted) return false
        loadedRef.current = true
        if (fresh.observation_version >= cursorRef.current) {
          cursorRef.current = fresh.observation_version
          setDecision(fresh)
          setObservationVersion(fresh.observation_version)
        }
        // Recovered only when the refetched snapshot reached the target.
        setDegraded(fresh.observation_version < target)
        return true
      } catch (error) {
        if (isAbort(error) || opts.signal?.aborted) return false
        if (error instanceof ApiError && error.code === 'not_found') {
          // Honest unknown match: no decision context exists.
          loadedRef.current = true
          if (cursorRef.current === 0) {
            setDecision(null)
            setObservationVersion(0)
          }
          setDegraded(false)
          return true
        }
        if (opts.initial) {
          setErrorCode(errorCodeOf(error))
          setPhase('error')
          return false
        }
        // Keep the last trusted view; the gap stays visible via degraded.
        setDegraded(true)
        return false
      }
    },
    [matchId],
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
        setPhase(loadedRef.current ? 'reconnecting' : 'loading')
        scheduleRetry()
      }, HEARTBEAT_TIMEOUT_MS)
    },
    [scheduleRetry],
  )

  const applyFrame = useCallback(
    (frame: DecisionStreamFrame, controller: AbortController) => {
      if (frame.id !== null) lastEventIdRef.current = frame.id
      switch (frame.type) {
        case 'ready': {
          const readyDecision = frame.payload.decision
          const version = frame.payload.observation_version
          if (readyDecision !== null && version >= cursorRef.current) {
            cursorRef.current = version
            loadedRef.current = true
            setDecision(readyDecision)
            setObservationVersion(version)
            setDegraded(false)
          }
          return
        }
        case 'decision_delta': {
          const version = frame.payload.observation_version
          if (version <= cursorRef.current) return // duplicate or stale
          if (version > cursorRef.current + 1) setDegraded(true)
          void fetchDecision(version, { initial: false, signal: controller.signal })
          return
        }
        case 'malformed':
          setDegraded(true)
          void fetchDecision(cursorRef.current + 1, {
            initial: false,
            signal: controller.signal,
          })
          return
        case 'heartbeat':
          return
      }
    },
    [fetchDecision],
  )

  const openStream = useCallback(async () => {
    if (!matchId) return
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const lastEventId =
      lastEventIdRef.current ??
      (cursorRef.current > 0 ? String(cursorRef.current) : null)
    try {
      const response = await openDecisionStream(matchId, {
        signal: controller.signal,
        lastEventId,
      })
      if (controller.signal.aborted) return
      setPhase('live')
      setErrorCode(null)
      resetWatchdog(controller)
      for await (const frame of parseDecisionStream(
        response.body as ReadableStream<Uint8Array>,
      )) {
        if (controller.signal.aborted) return
        resetWatchdog(controller)
        applyFrame(frame, controller)
      }
      if (!controller.signal.aborted) {
        setPhase(loadedRef.current ? 'reconnecting' : 'loading')
        scheduleRetry()
      }
    } catch (error) {
      if (isAbort(error) || controller.signal.aborted) return
      if (loadedRef.current) {
        setPhase('reconnecting')
        scheduleRetry()
      } else {
        setErrorCode(errorCodeOf(error))
        setPhase('error')
      }
    }
  }, [matchId, applyFrame, resetWatchdog, scheduleRetry])

  openStreamRef.current = openStream

  const refresh = useCallback(async () => {
    if (!matchId) return
    if (retryRef.current !== null) {
      window.clearTimeout(retryRef.current)
      retryRef.current = null
    }
    setPhase('loading')
    await fetchDecision(cursorRef.current, { initial: true })
    await openStream()
  }, [matchId, fetchDecision, openStream])

  useEffect(() => {
    if (!matchId) return
    let cancelled = false
    cursorRef.current = 0
    loadedRef.current = false
    lastEventIdRef.current = null
    setDecision(null)
    setObservationVersion(0)
    setDegraded(false)
    setErrorCode(null)
    setPhase('loading')

    void (async () => {
      // Snapshot first: the REST decision is the authority before any frame.
      const loaded = await fetchDecision(0, { initial: true })
      if (cancelled || !loaded) return
      await openStream()
    })()

    return () => {
      cancelled = true
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
  }, [matchId, fetchDecision, openStream])

  return { decision, observationVersion, phase, degraded, errorCode, refresh }
}
