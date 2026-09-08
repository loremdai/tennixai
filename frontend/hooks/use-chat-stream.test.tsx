import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { ChatEvent } from '@/lib/api/types'
import { useChatStream } from './use-chat-stream'

const { streamChatMock } = vi.hoisted(() => ({ streamChatMock: vi.fn() }))

vi.mock('@/lib/api/client', () => ({
  streamChat: streamChatMock,
}))

type ScriptedOptions = {
  failWith?: Error
  abortSignalCheck?: boolean
}

function scriptedStream(events: ChatEvent[], options: ScriptedOptions = {}) {
  return (request: unknown, signal?: AbortSignal) => {
    async function* generate(): AsyncGenerator<ChatEvent> {
      for (const event of events) {
        if (signal?.aborted) {
          throw new DOMException('The operation was aborted.', 'AbortError')
        }
        yield event
        await Promise.resolve()
      }
      if (options.failWith) {
        if (signal?.aborted) {
          throw new DOMException('The operation was aborted.', 'AbortError')
        }
        throw options.failWith
      }
    }
    return generate()
  }
}

const dataEvent: ChatEvent = {
  type: 'data',
  payload: {
    kind: 'matches',
    matches: [
      {
        id: 'mat_1',
        status: 'live',
        players: [
          { id: 'ply_1', name: 'Jannik Sinner', country_code: 'ita', ranking: 1 },
          { id: 'ply_2', name: 'Carlos Alcaraz', country_code: 'esp', ranking: 2 },
        ],
        tournament: { id: 'trn_1', name: 'ATP Finals', tour: 'atp' },
        scheduled_at: '2026-09-08T10:00:00Z',
        round: 'Semifinal',
        surface: 'hard',
        indoor: true,
        format: 'BO3',
        live_state: null,
        winner_player_id: null,
        freshness: {
          provider: 'fake',
          source_updated_at: null,
          observed_at: '2026-09-08T10:00:00Z',
          is_stale: false,
          age_seconds: 0,
        },
      },
    ],
  },
}

beforeEach(() => {
  streamChatMock.mockReset()
})

describe('useChatStream', () => {
  it('starts idle and streams data and text to success', async () => {
    streamChatMock.mockImplementation(
      scriptedStream([
        { type: 'status', payload: { stage: 'resolving' } },
        dataEvent,
        { type: 'text_delta', payload: { delta: 'Sinner ' } },
        { type: 'text_delta', payload: { delta: '今晚出场。' } },
        { type: 'done', payload: { ok: true } },
      ]),
    )

    const { result } = renderHook(() => useChatStream('global'))

    expect(result.current.state.phase).toBe('idle')

    await act(async () => {
      await result.current.send('Sinner 今晚几点比赛？')
    })

    expect(result.current.state.phase).toBe('success')
    expect(result.current.state.question).toBe('Sinner 今晚几点比赛？')
    expect(result.current.state.text).toBe('Sinner 今晚出场。')
    expect(result.current.state.data).toEqual(dataEvent.payload)
    expect(result.current.state.error).toBeNull()
  })

  it('sends match scope with the internal match id', async () => {
    streamChatMock.mockImplementation(scriptedStream([{ type: 'done', payload: { ok: true } }]))

    const { result } = renderHook(() => useChatStream('match', 'mat_42'))

    await act(async () => {
      await result.current.send('谁在发球？')
    })

    const [request] = streamChatMock.mock.calls[0]
    expect(request.scope).toBe('match')
    expect(request.match_id).toBe('mat_42')
    expect(request.messages).toEqual([{ role: 'user', content: '谁在发球？' }])
  })

  it('keeps structured data when the terminal error event arrives', async () => {
    streamChatMock.mockImplementation(
      scriptedStream([
        dataEvent,
        { type: 'text_delta', payload: { delta: '比赛数据已找到，但 AI 说明暂时不可用。' } },
        { type: 'error', payload: { code: 'llm_unavailable', message: 'LLM streaming failed', details: {} } },
      ]),
    )

    const { result } = renderHook(() => useChatStream('global'))

    await act(async () => {
      await result.current.send('现在比分多少？')
    })

    expect(result.current.state.phase).toBe('error')
    expect(result.current.state.error?.code).toBe('llm_unavailable')
    expect(result.current.state.data).toEqual(dataEvent.payload)
    expect(result.current.state.text).toBe('比赛数据已找到，但 AI 说明暂时不可用。')
  })

  it('preserves provider error details for rate-limit UX', async () => {
    streamChatMock.mockImplementation(
      scriptedStream([
        {
          type: 'error',
          payload: { code: 'rate_limited', message: 'quota exceeded', details: { retry_after: '30' } },
        },
      ]),
    )

    const { result } = renderHook(() => useChatStream('global'))

    await act(async () => {
      await result.current.send('郑钦文下一场比赛是什么时候？')
    })

    expect(result.current.state.error?.code).toBe('rate_limited')
    expect(result.current.state.error?.details).toEqual({ retry_after: '30' })
  })

  it('surfaces transport failures as typed errors', async () => {
    streamChatMock.mockImplementation(scriptedStream([], { failWith: new Error('network down') }))

    const { result } = renderHook(() => useChatStream('global'))

    await act(async () => {
      await result.current.send('今晚有比赛吗？')
    })

    expect(result.current.state.phase).toBe('error')
    expect(result.current.state.error?.code).toBe('internal_error')
  })

  it('aborts the previous request when a new one starts', async () => {
    const signals: (AbortSignal | undefined)[] = []
    streamChatMock.mockImplementation((request: unknown, signal?: AbortSignal) => {
      signals.push(signal)
      return scriptedStream([
        { type: 'text_delta', payload: { delta: '第一次' } },
        { type: 'done', payload: { ok: true } },
      ])(request, signal)
    })

    const { result } = renderHook(() => useChatStream('global'))

    await act(async () => {
      const first = result.current.send('问题一')
      const second = result.current.send('问题二')
      await Promise.allSettled([first, second])
    })

    expect(signals.length).toBe(2)
    expect(signals[0]?.aborted).toBe(true)
    await waitFor(() => {
      expect(result.current.state.question).toBe('问题二')
    })
  })

  it('cancel stops the stream without an error state', async () => {
    streamChatMock.mockImplementation(
      scriptedStream(
        [
          { type: 'text_delta', payload: { delta: '部分内容' } },
          { type: 'text_delta', payload: { delta: '不会到达' } },
          { type: 'done', payload: { ok: true } },
        ],
        {},
      ),
    )

    const { result } = renderHook(() => useChatStream('global'))

    await act(async () => {
      const pending = result.current.send('问题')
      result.current.cancel()
      await pending
    })

    expect(result.current.state.phase).not.toBe('streaming')
    expect(result.current.state.phase).not.toBe('loading')
    expect(result.current.state.error).toBeNull()
  })

  it('reset returns to idle', async () => {
    streamChatMock.mockImplementation(scriptedStream([{ type: 'done', payload: { ok: true } }]))

    const { result } = renderHook(() => useChatStream('global'))

    await act(async () => {
      await result.current.send('问题')
    })
    act(() => {
      result.current.reset()
    })

    expect(result.current.state).toEqual({
      phase: 'idle',
      question: '',
      text: '',
      data: null,
      error: null,
    })
  })

  it('bounds the message history to 12 entries', async () => {
    streamChatMock.mockImplementation(scriptedStream([{ type: 'done', payload: { ok: true } }]))

    const { result } = renderHook(() => useChatStream('global'))

    await act(async () => {
      for (let index = 0; index < 14; index += 1) {
        // eslint-disable-next-line no-await-in-loop
        await result.current.send(`问题 ${index}`)
      }
    })

    const lastRequest = streamChatMock.mock.calls.at(-1)?.[0]
    expect(lastRequest.messages.length).toBeLessThanOrEqual(12)
    expect(lastRequest.messages.at(-1)).toEqual({ role: 'user', content: '问题 13' })
  })

  it('unmount aborts the active stream', async () => {
    const signals: (AbortSignal | undefined)[] = []
    streamChatMock.mockImplementation((request: unknown, signal?: AbortSignal) => {
      signals.push(signal)
      async function* generate(): AsyncGenerator<ChatEvent> {
        yield { type: 'status', payload: { stage: 'resolving' } }
        await new Promise((resolve) => setTimeout(resolve, 50))
        if (signal?.aborted) {
          throw new DOMException('The operation was aborted.', 'AbortError')
        }
        yield { type: 'done', payload: { ok: true } }
      }
      return generate()
    })

    const { result, unmount } = renderHook(() => useChatStream('global'))

    act(() => {
      void result.current.send('问题')
    })
    unmount()

    await waitFor(() => {
      expect(signals[0]?.aborted).toBe(true)
    })
  })
})
