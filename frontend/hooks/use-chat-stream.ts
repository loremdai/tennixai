'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

import { streamChat } from '@/lib/api/client'
import type { AnswerContextDto, ChatWarning, StructuredData } from '@/lib/api/types'

export type ChatProgress = {
  completed: number
  total: number
  tool: string | null
}

export type ChatViewState = {
  phase: 'idle' | 'loading' | 'streaming' | 'success' | 'error'
  stage: string | null
  question: string
  text: string
  data: StructuredData | null
  answerContext: AnswerContextDto | null
  error: { code: string; message: string; details: Record<string, unknown> } | null
  warnings: ChatWarning[]
  progress: ChatProgress | null
}

type HistoryMessage = { role: 'user' | 'assistant'; content: string }

const MAX_HISTORY = 12

const IDLE_STATE: ChatViewState = {
  phase: 'idle',
  stage: null,
  question: '',
  text: '',
  data: null,
  answerContext: null,
  error: null,
  warnings: [],
  progress: null,
}

const CHAT_STAGE_LABELS: Record<string, string> = {
  resolving: '正在锁定比赛快照…',
  planning: '正在拆解问题…',
  fetching_data: '正在读取比赛数据…',
  generating: '正在组织回答…',
}

export function chatStageLabel(stage: string | null): string {
  return (stage && CHAT_STAGE_LABELS[stage]) || '正在查询…'
}

export function chatProgressLabel(stage: string | null, progress: ChatProgress | null): string {
  const label = chatStageLabel(stage)
  if (!progress || progress.total <= 0 || progress.completed < 0) return label
  return `${label}（${progress.completed}/${progress.total}）`
}

function chatProgressFromStatus(payload: {
  completed?: number
  total?: number
  tool?: string | null
}): ChatProgress | null {
  if (
    !Number.isInteger(payload.completed) ||
    !Number.isInteger(payload.total) ||
    payload.completed === undefined ||
    payload.total === undefined ||
    payload.completed < 0 ||
    payload.total <= 0
  ) {
    return null
  }
  return {
    completed: payload.completed,
    total: payload.total,
    tool: payload.tool ?? null,
  }
}

function getErrorDetails(error: unknown): Record<string, unknown> {
  if (typeof error !== 'object' || error === null || !('details' in error)) {
    return {}
  }
  const details = (error as { details: unknown }).details
  return typeof details === 'object' && details !== null && !Array.isArray(details)
    ? (details as Record<string, unknown>)
    : {}
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
      setState({
        phase: 'loading',
        stage: null,
        question: prompt,
        text: '',
        data: null,
        answerContext: null,
        error: null,
        warnings: [],
        progress: null,
      })

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
              setState((current) => ({
                ...current,
                stage: event.payload.stage,
                progress: chatProgressFromStatus(event.payload),
              }))
              break
            case 'data':
              setState((current) => ({
                ...current,
                phase: 'streaming',
                stage: 'fetching_data',
                progress: null,
                data: event.payload,
                answerContext: current.answerContext ?? event.payload.answer_context ?? null,
              }))
              break
            case 'text_delta':
              text += event.payload.delta
              setState((current) => ({
                ...current,
                phase: 'streaming',
                stage: 'generating',
                progress: null,
                text,
              }))
              break
            case 'warning':
              setState((current) => ({
                ...current,
                warnings: [...current.warnings, event.payload],
              }))
              break
            case 'error':
              terminated = true
              setState((current) => ({
                ...current,
                phase: 'error',
                stage: null,
                progress: null,
                error: {
                  code: event.payload.code,
                  message: event.payload.message,
                  details: event.payload.details ?? {},
                },
              }))
              break
            case 'done':
              terminated = true
              setState((current) => ({ ...current, phase: 'success', stage: null, progress: null }))
              break
          }
          if (terminated) break
        }

        if (!mountedRef.current || controller.signal.aborted) return
        if (!terminated) {
          setState((current) => ({ ...current, phase: 'success', stage: null, progress: null }))
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
        setState((current) => ({
          ...current,
          phase: 'error',
          stage: null,
          progress: null,
          error: { code, message, details: getErrorDetails(error) },
        }))
      }
    },
    [scope, matchId],
  )

  const cancel = useCallback(() => {
    abortRef.current?.abort()
    setState((current) =>
      current.phase === 'loading' || current.phase === 'streaming'
        ? { ...current, phase: 'idle', stage: null, warnings: [], progress: null }
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
