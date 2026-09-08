import type { ChatEvent, ChatRequest, MatchDto, PlayerDto } from './types'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

async function toApiError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as {
      error?: { code?: string; message?: string; details?: Record<string, unknown> }
    }
    return new ApiError(
      response.status,
      body.error?.code ?? 'internal_error',
      body.error?.message ?? `Request failed with status ${response.status}`,
      body.error?.details ?? {},
    )
  } catch {
    return new ApiError(response.status, 'internal_error', `Request failed with status ${response.status}`)
  }
}

async function requestJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { cache: 'no-store', signal })
  if (!response.ok) {
    throw await toApiError(response)
  }
  const body = (await response.json()) as { data: T }
  return body.data
}

export function getPlayers(query: string, signal?: AbortSignal): Promise<PlayerDto[]> {
  return requestJson<PlayerDto[]>(`/api/players/search?q=${encodeURIComponent(query)}`, signal)
}

export function getMatches(
  status: 'live' | 'upcoming',
  player?: string,
  signal?: AbortSignal,
): Promise<MatchDto[]> {
  const params = new URLSearchParams({ status })
  if (player) params.set('player', player)
  return requestJson<MatchDto[]>(`/api/matches?${params.toString()}`, signal)
}

export function getMatch(matchId: string, signal?: AbortSignal): Promise<MatchDto> {
  return requestJson<MatchDto>(`/api/matches/${encodeURIComponent(matchId)}`, signal)
}

function parseFrame(frame: string): ChatEvent | null {
  let type: string | null = null
  const dataLines: string[] = []
  for (const line of frame.split(/\r?\n/)) {
    if (!line || line.startsWith(':')) continue
    if (line.startsWith('event:')) {
      type = line.slice('event:'.length).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trim())
    }
  }
  if (!type || dataLines.length === 0) return null
  return { type, payload: JSON.parse(dataLines.join('\n')) } as ChatEvent
}

export async function* parseSse(stream: ReadableStream<Uint8Array>): AsyncGenerator<ChatEvent> {
  const decoder = new TextDecoder()
  const reader = stream.getReader()
  let buffer = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const frames = buffer.split(/\r?\n\r?\n/)
      buffer = frames.pop() ?? ''
      for (const frame of frames) {
        const event = parseFrame(frame)
        if (event) yield event
      }
    }
    buffer += decoder.decode()
    if (buffer.trim()) {
      const event = parseFrame(buffer)
      if (event) yield event
    }
  } finally {
    reader.releaseLock()
  }
}

export async function* streamChat(
  request: ChatRequest,
  signal?: AbortSignal,
): AsyncGenerator<ChatEvent> {
  let response: Response
  try {
    response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
      cache: 'no-store',
      signal,
    })
  } catch (error) {
    if (isAbortError(error)) throw error
    throw new ApiError(502, 'internal_error', 'Chat stream request failed')
  }

  if (!response.ok) {
    throw await toApiError(response)
  }
  if (!response.body) {
    throw new ApiError(502, 'internal_error', 'Chat stream has no body')
  }

  yield* parseSse(response.body)
}
