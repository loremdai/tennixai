import { useCallback, useEffect, useRef, useState } from 'react'

import { getMatchSnapshot, openMatchStream, parseMatchStream } from '@/lib/api/client'
import type { MatchSnapshotDto } from '@/lib/api/types'

export type MatchStreamPhase = 'loading' | 'live' | 'reconnecting' | 'stale' | 'ended' | 'error'

export type MatchStreamState = {
  snapshot: MatchSnapshotDto | null
  phase: MatchStreamPhase
  errorCode: string | null
  refresh: () => Promise<void>
}

const HIDDEN_RELEASE_MS = 60_000
const RETRY_MS = 2_000

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

export function useMatchStream(matchId: string | undefined): MatchStreamState {
  const [snapshot, setSnapshot] = useState<MatchSnapshotDto | null>(null)
  const [phase, setPhase] = useState<MatchStreamPhase>('loading')
  const [errorCode, setErrorCode] = useState<string | null>(null)

  const versionRef = useRef(0)
  const abortRef = useRef<AbortController | null>(null)
  const retryRef = useRef<number | null>(null)
  const hiddenTimerRef = useRef<number | null>(null)
  const endedRef = useRef(false)
  const hasSnapshotRef = useRef(false)
  const openStreamRef = useRef<() => Promise<void>>(async () => {})

  const applySnapshot = useCallback((next: MatchSnapshotDto) => {
    versionRef.current = next.state_version
    hasSnapshotRef.current = true
    setSnapshot(next)
  }, [])

  const loadSnapshot = useCallback(
    async (signal?: AbortSignal) => {
      if (!matchId) return
      applySnapshot(await getMatchSnapshot(matchId, signal))
    },
    [matchId, applySnapshot],
  )

  const scheduleRetry = useCallback(() => {
    if (retryRef.current !== null) return
    retryRef.current = window.setTimeout(() => {
      retryRef.current = null
      void openStreamRef.current()
    }, RETRY_MS)
  }, [])

  const openStream = useCallback(async () => {
    if (!matchId || endedRef.current) return
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    try {
      const response = await openMatchStream(matchId, { signal: controller.signal })
      if (controller.signal.aborted) return
      setPhase('live')
      for await (const frame of parseMatchStream(response.body as ReadableStream<Uint8Array>)) {
        if (controller.signal.aborted) return
        if (frame.type === 'ready') {
          applySnapshot(frame.payload.snapshot)
        } else if (frame.type === 'match_delta') {
          const version = frame.payload.state_version
          if (version <= versionRef.current) continue
          if (version === versionRef.current + 1) {
            applySnapshot(frame.payload.snapshot)
          } else {
            await loadSnapshot(controller.signal)
          }
        } else if (frame.type === 'match_ended') {
          endedRef.current = true
          setPhase('ended')
          return
        } else if (frame.type === 'error') {
          setErrorCode(frame.payload.code)
          setPhase('error')
          return
        }
      }
      if (!endedRef.current && !controller.signal.aborted) {
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
  }, [matchId, applySnapshot, loadSnapshot, scheduleRetry])

  openStreamRef.current = openStream

  const refresh = useCallback(async () => {
    if (!matchId) return
    if (retryRef.current !== null) {
      window.clearTimeout(retryRef.current)
      retryRef.current = null
    }
    setPhase('loading')
    try {
      await loadSnapshot()
      setPhase('live')
      await openStream()
    } catch (error) {
      setErrorCode(errorCodeOf(error))
      setPhase('error')
    }
  }, [matchId, loadSnapshot, openStream])

  useEffect(() => {
    if (!matchId) return
    let cancelled = false
    endedRef.current = false
    hasSnapshotRef.current = false
    setSnapshot(null)
    setErrorCode(null)
    setPhase('loading')

    void (async () => {
      try {
        await loadSnapshot()
        if (cancelled) return
        await openStream()
      } catch (error) {
        if (cancelled) return
        setErrorCode(errorCodeOf(error))
        setPhase('error')
      }
    })()

    const onVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        hiddenTimerRef.current = window.setTimeout(() => {
          hiddenTimerRef.current = null
          abortRef.current?.abort()
          if (!endedRef.current) setPhase('stale')
        }, HIDDEN_RELEASE_MS)
        return
      }
      if (hiddenTimerRef.current !== null) {
        window.clearTimeout(hiddenTimerRef.current)
        hiddenTimerRef.current = null
      }
      if (cancelled || endedRef.current) return
      void (async () => {
        try {
          await loadSnapshot()
          if (cancelled) return
          await openStream()
        } catch {
          if (!cancelled) {
            setPhase('reconnecting')
            scheduleRetry()
          }
        }
      })()
    }
    document.addEventListener('visibilitychange', onVisibilityChange)

    return () => {
      cancelled = true
      document.removeEventListener('visibilitychange', onVisibilityChange)
      if (hiddenTimerRef.current !== null) {
        window.clearTimeout(hiddenTimerRef.current)
        hiddenTimerRef.current = null
      }
      if (retryRef.current !== null) {
        window.clearTimeout(retryRef.current)
        retryRef.current = null
      }
      abortRef.current?.abort()
    }
  }, [matchId, loadSnapshot, openStream, scheduleRetry])

  return { snapshot, phase, errorCode, refresh }
}
