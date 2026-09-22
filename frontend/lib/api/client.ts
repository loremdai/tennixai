import type {
  ChatEvent,
  ChatRequest,
  CircuitTier,
  MatchCatalogDto,
  MatchDto,
  MatchFiltersDto,
  MatchSnapshotDto,
  MatchStreamFrame,
  PlayerDto,
  PlayerProfileViewDto,
  PlayerResultPageDto,
  PlayerSearchResolutionDto,
  RankingPageDto,
} from './types'
import {
  CIRCUIT_ORDER,
  DISCIPLINE_ORDER,
  GENDER_ORDER,
} from '@/lib/match-filters'

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
  // The API uses an omitted group for its approved defaults. Expand the
  // frontend's empty="all" state so both contracts remain expressible.
  for (const circuit of filters.circuits.length ? filters.circuits : CIRCUIT_ORDER) {
    params.append('circuit', circuit)
  }
  for (const gender of filters.genders.length ? filters.genders : GENDER_ORDER) {
    params.append('gender', gender)
  }
  for (const discipline of filters.disciplines.length ? filters.disciplines : DISCIPLINE_ORDER) {
    params.append('discipline', discipline)
  }
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

// ---------------------------------------------------------------------------
// P2.6 player directory clients
// ---------------------------------------------------------------------------

export function getPlayerRankings(
  params: { tour: 'ATP' | 'WTA'; page: number; country?: string },
  signal?: AbortSignal,
): Promise<RankingPageDto> {
  const search = new URLSearchParams({ tour: params.tour, page: String(params.page) })
  if (params.country) search.set('country', params.country)
  return requestJson<RankingPageDto>(`/api/players/rankings?${search.toString()}`, signal)
}

export function searchPlayerDirectory(
  query: string,
  limit = 10,
  signal?: AbortSignal,
): Promise<PlayerSearchResolutionDto> {
  const search = new URLSearchParams({ q: query, limit: String(limit) })
  return requestJson<PlayerSearchResolutionDto>(`/api/players/search?${search.toString()}`, signal)
}

export function getPlayerProfile(
  playerId: string,
  season?: number,
  signal?: AbortSignal,
): Promise<PlayerProfileViewDto> {
  const search = new URLSearchParams()
  if (season !== undefined) search.set('season', String(season))
  const query = search.toString()
  return requestJson<PlayerProfileViewDto>(
    `/api/players/${encodeURIComponent(playerId)}${query ? `?${query}` : ''}`,
    signal,
  )
}

export function getPlayerResults(
  playerId: string,
  params: {
    season: number
    tiers?: CircuitTier[]
    outcome?: 'all' | 'won' | 'lost'
    page: number
  },
  signal?: AbortSignal,
): Promise<PlayerResultPageDto> {
  const search = new URLSearchParams({
    season: String(params.season),
    page: String(params.page),
  })
  for (const tier of params.tiers ?? []) search.append('tier', tier)
  if (params.outcome) search.set('outcome', params.outcome)
  return requestJson<PlayerResultPageDto>(
    `/api/players/${encodeURIComponent(playerId)}/results?${search.toString()}`,
    signal,
  )
}

// ---------------------------------------------------------------------------
// P3 market decision support clients (T67). Every payload passes a runtime
// decoder; unknown enums or malformed shapes fail visibly (P3DecodeError)
// instead of being coerced. Stream parsers convert undecodable frames into
// explicit `malformed` events so hooks can degrade without losing the stream.
// ---------------------------------------------------------------------------

import {
  decodeDecisionStreamEvent,
  decodeMarketPage,
  decodeMarketStreamEvent,
  decodeMatchDecision,
  decodeOpportunityList,
  decodePaperPositions,
  decodePulse,
} from './p3-types'
import type {
  DecisionSnapshotDto,
  DecisionStreamEvent,
  Gender,
  MarketPageDto,
  MarketPhase,
  MarketStreamEvent,
  OpportunityAvailabilityDto,
  OpportunityDto,
  PaperPositionsViewDto,
  PulseViewDto,
} from './types'

async function requestP3<T>(
  path: string,
  decode: (body: unknown) => T,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(path, { cache: 'no-store', signal })
  if (!response.ok) {
    throw await toApiError(response)
  }
  return decode(await response.json())
}

export type OpportunityView = {
  rows: OpportunityDto[]
  /** Why the view looks the way it does; null only on older payloads. */
  availability: OpportunityAvailabilityDto | null
}

export function listMarketOpportunities(
  signal?: AbortSignal,
): Promise<OpportunityView> {
  return requestP3('/api/markets/opportunities', decodeOpportunityList, signal)
}

export type MarketListParams = {
  tier?: CircuitTier
  gender?: Gender
  phase?: MarketPhase
  page?: number
  pageSize?: number
}

export function listMarkets(params: MarketListParams = {}, signal?: AbortSignal): Promise<MarketPageDto> {
  const search = new URLSearchParams()
  if (params.tier) search.set('tier', params.tier)
  if (params.gender) search.set('gender', params.gender)
  if (params.phase) search.set('phase', params.phase)
  if (params.page !== undefined) search.set('page', String(params.page))
  if (params.pageSize !== undefined) search.set('page_size', String(params.pageSize))
  const query = search.toString()
  return requestP3(`/api/markets${query ? `?${query}` : ''}`, decodeMarketPage, signal)
}

export function getPaperPositions(signal?: AbortSignal): Promise<PaperPositionsViewDto> {
  return requestP3('/api/paper/positions', decodePaperPositions, signal)
}

export function getMarketPulse(signal?: AbortSignal): Promise<PulseViewDto> {
  return requestP3('/api/markets/pulse', decodePulse, signal)
}

export function getMatchDecision(
  matchId: string,
  signal?: AbortSignal,
): Promise<DecisionSnapshotDto> {
  return requestP3(
    `/api/matches/${encodeURIComponent(matchId)}/decision`,
    decodeMatchDecision,
    signal,
  )
}

async function openP3Stream(
  path: string,
  options: { signal?: AbortSignal; lastEventId?: string | null },
): Promise<Response> {
  const headers: Record<string, string> = { Accept: 'text/event-stream' }
  if (options.lastEventId) headers['Last-Event-ID'] = options.lastEventId
  let response: Response
  try {
    response = await fetch(path, { cache: 'no-store', headers, signal: options.signal })
  } catch (error) {
    if (isAbortError(error)) throw error
    throw new ApiError(502, 'internal_error', 'P3 stream request failed')
  }
  if (!response.ok) throw await toApiError(response)
  if (!response.body) throw new ApiError(502, 'internal_error', 'P3 stream has no body')
  return response
}

export function openMarketStream(
  options: { signal?: AbortSignal; lastEventId?: string | null } = {},
): Promise<Response> {
  return openP3Stream('/api/markets/stream', options)
}

export function openDecisionStream(
  matchId: string,
  options: { signal?: AbortSignal; lastEventId?: string | null } = {},
): Promise<Response> {
  return openP3Stream(
    `/api/matches/${encodeURIComponent(matchId)}/decision/stream`,
    options,
  )
}

type RawSseFrame = { type: string; id: string | null; data: string }

function parseRawSseFrame(frame: string): RawSseFrame | null {
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
  if (!type) return null
  return { type, id, data: dataLines.join('\n') }
}

async function* splitSseFrames(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<RawSseFrame> {
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
        const parsed = parseRawSseFrame(frame)
        if (parsed) yield parsed
      }
    }
    buffer += decoder.decode()
    if (buffer.trim()) {
      const parsed = parseRawSseFrame(buffer)
      if (parsed) yield parsed
    }
  } finally {
    reader.releaseLock()
  }
}

export type MarketStreamFrame = MarketStreamEvent & { id: string | null }
export type DecisionStreamFrame = DecisionStreamEvent & { id: string | null }

export async function* parseMarketStream(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<MarketStreamFrame> {
  for await (const rawFrame of splitSseFrames(stream)) {
    try {
      const payload: unknown = rawFrame.data ? JSON.parse(rawFrame.data) : {}
      const event = decodeMarketStreamEvent(rawFrame.type, payload)
      yield Object.assign({ id: rawFrame.id }, event) as MarketStreamFrame
    } catch {
      yield {
        type: 'malformed',
        id: rawFrame.id,
        payload: { reason: `undecodable ${rawFrame.type} frame` },
      }
    }
  }
}

export async function* parseDecisionStream(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<DecisionStreamFrame> {
  for await (const rawFrame of splitSseFrames(stream)) {
    try {
      const payload: unknown = rawFrame.data ? JSON.parse(rawFrame.data) : {}
      const event = decodeDecisionStreamEvent(rawFrame.type, payload)
      yield Object.assign({ id: rawFrame.id }, event) as DecisionStreamFrame
    } catch {
      yield {
        type: 'malformed',
        id: rawFrame.id,
        payload: { reason: `undecodable ${rawFrame.type} frame` },
      }
    }
  }
}
