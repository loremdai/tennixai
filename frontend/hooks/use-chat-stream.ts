'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

import { streamChat } from '@/lib/api/client'
import type { StructuredData } from '@/lib/api/types'

export type ChatViewState = {
  phase: 'idle' | 'loading' | 'streaming' | 'success' | 'error'
  question: string
  text: string
  data: StructuredData | null
  error: { code: string; message: string } | null
}

type HistoryMessage = { role: 'user' | 'assistant'; content: string }

const MAX_HISTORY = 12

const IDLE_STATE: ChatViewState = {
  phase: 'idle',
  question: '',
  text: '',
  data: null,
  error: null,
}

export function useChatStream(scope: 'global' | 'match', matchId?: string): {
  state: ChatViewState
  send: (prompt: string) => Promise<void>
  cancel: () => void
  reset: () => void
} {
  const [state, setState] = useState<ChatViewState>(IDLE_STATE)
  const historyRef = useRef<HistoryMessage[]>([])
  const abortRef = useRef<AbortController | null>(null)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      abortRef.current?.abort()
    }
  }, [])

  const send = useCallback(
    async (prompt: string) => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      historyRef.current = [
        ...historyRef.current,
        { role: 'user' as const, content: prompt },
      ].slice(-MAX_HISTORY)
      setState({ phase: 'loading', question: prompt, text: '', data: null, error: null })

      let text = ''
      let terminated = false

      try {
        const stream = streamChat(
          { scope, match_id: matchId, messages: historyRef.current },
          controller.signal,
        )
        for await (const event of stream) {
          if (!mountedRef.current || controller.signal.aborted) return
          switch (event.type) {
            case 'status':
              break
            case 'data':
              setState((current) => ({ ...current, phase: 'streaming', data: event.payload }))
              break
            case 'text_delta':
              text += event.payload.delta
              setState((current) => ({ ...current, phase: 'streaming', text }))
              break
            case 'error':
              terminated = true
              setState((current) => ({
                ...current,
                phase: 'error',
                error: { code: event.payload.code, message: event.payload.message },
              }))
              break
            case 'done':
              terminated = true
              setState((current) => ({ ...current, phase: 'success' }))
              break
          }
          if (terminated) break
        }

        if (!mountedRef.current || controller.signal.aborted) return
        if (!terminated) {
          setState((current) => ({ ...current, phase: 'success' }))
        }
        if (text) {
          historyRef.current = [
            ...historyRef.current,
            { role: 'assistant' as const, content: text },
          ].slice(-MAX_HISTORY)
        }
      } catch (error) {
        if (!mountedRef.current || controller.signal.aborted) return
        if (error instanceof DOMException && error.name === 'AbortError') return
        const code =
          typeof error === 'object' && error !== null && 'code' in error
            ? String((error as { code: unknown }).code)
            : 'internal_error'
        const message = error instanceof Error ? error.message : 'Chat stream failed'
        setState((current) => ({ ...current, phase: 'error', error: { code, message } }))
      }
    },
    [scope, matchId],
  )

  const cancel = useCallback(() => {
    abortRef.current?.abort()
    setState((current) =>
      current.phase === 'loading' || current.phase === 'streaming'
        ? { ...current, phase: 'idle' }
        : current,
    )
  }, [])

  const reset = useCallback(() => {
    abortRef.current?.abort()
    historyRef.current = []
    setState(IDLE_STATE)
  }, [])

  return { state, send, cancel, reset }
}
