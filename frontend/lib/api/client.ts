import type {
  ChatEvent,
  ChatRequest,
  MatchCatalogDto,
  MatchDto,
  MatchFiltersDto,
  MatchSnapshotDto,
  MatchStreamFrame,
  PlayerDto,
} from './types'

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

export function getMatchSnapshot(
  matchId: string,
  signal?: AbortSignal,
): Promise<MatchSnapshotDto> {
  return requestJson<MatchSnapshotDto>(`/api/matches/${encodeURIComponent(matchId)}`, signal)
}

export async function openMatchStream(
  matchId: string,
  options: { signal?: AbortSignal; lastEventId?: string | null } = {},
): Promise<Response> {
  const headers: Record<string, string> = { Accept: 'text/event-stream' }
  if (options.lastEventId) headers['Last-Event-ID'] = options.lastEventId
  let response: Response
  try {
    response = await fetch(`/api/matches/${encodeURIComponent(matchId)}/stream`, {
      cache: 'no-store',
      headers,
      signal: options.signal,
    })
  } catch (error) {
    if (isAbortError(error)) throw error
    throw new ApiError(502, 'internal_error', 'Match stream request failed')
  }
  if (!response.ok) throw await toApiError(response)
  if (!response.body) throw new ApiError(502, 'internal_error', 'Match stream has no body')
  return response
}

export async function* parseMatchStream(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<MatchStreamFrame> {
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
        const parsed = parseMatchFrame(frame)
        if (parsed) yield parsed
      }
    }
    buffer += decoder.decode()
    if (buffer.trim()) {
      const parsed = parseMatchFrame(buffer)
      if (parsed) yield parsed
    }
  } finally {
    reader.releaseLock()
  }
}

function parseMatchFrame(frame: string): MatchStreamFrame | null {
  let type: string | null = null
  let id: string | null = null
  const dataLines: string[] = []
  for (const line of frame.split(/\r?\n/)) {
    if (!line || line.startsWith(':')) continue
    if (line.startsWith('event:')) {
      type = line.slice('event:'.length).trim()
    } else if (line.startsWith('id:')) {
      id = line.slice('id:'.length).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trim())
    }
  }
  if (!type || dataLines.length === 0) return null
  return { type, id, payload: JSON.parse(dataLines.join('\n')) } as MatchStreamFrame
}

export function getMatchCatalog(
  status: 'live' | 'upcoming',
  filters: MatchFiltersDto,
  signal?: AbortSignal,
): Promise<MatchCatalogDto> {
  const params = new URLSearchParams({ status })
  // Empty facet groups are omitted: the backend treats a missing group as
  // "all values", matching the shared Home filter semantics.
  for (const circuit of filters.circuits) params.append('circuit', circuit)
  for (const gender of filters.genders) params.append('gender', gender)
  for (const discipline of filters.disciplines) params.append('discipline', discipline)
  return requestJson<MatchCatalogDto>(`/api/matches/catalog?${params.toString()}`, signal)
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
