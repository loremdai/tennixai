export type MatchStatus = 'scheduled' | 'live' | 'finished' | 'cancelled' | 'postponed' | 'unknown'

export type CircuitTier = 'atp' | 'wta' | 'challenger' | 'itf' | 'other'
export type Gender = 'men' | 'women' | 'mixed' | 'unknown'
export type Discipline = 'singles' | 'doubles' | 'team' | 'unknown'
export type CapabilityStatus = 'available' | 'partial' | 'unavailable' | 'stale'
export type ConnectionStatus =
  | 'connecting'
  | 'live'
  | 'reconnecting'
  | 'stale'
  | 'ended'
  | 'unavailable'

export type PlayerDto = { id: string; name: string; country_code: string | null; ranking: number | null }
export type TournamentDto = {
  id: string
  name: string
  tour: string | null
  circuit?: CircuitTier
  gender?: Gender
  discipline?: Discipline
}
export type SetScoreDto = { number: number; player1_games: number | null; player2_games: number | null }
export type MatchScoreDto = {
  sets_won: [number, number]
  sets: SetScoreDto[]
  points: [string | null, string | null]
  is_tiebreak: boolean
}
export type LiveStateDto = {
  score: MatchScoreDto | null
  server_player_id: string | null
  state_version?: number
  connection_status?: ConnectionStatus
  last_event_at?: string | null
  as_of?: string | null
}
export type MatchDto = {
  id: string
  status: MatchStatus
  players: [PlayerDto, PlayerDto]
  tournament: TournamentDto
  scheduled_at: string | null
  round: string | null
  surface: string | null
  indoor: boolean | null
  format: string | null
  live_state: LiveStateDto | null
  winner_player_id: string | null
  freshness: {
    provider: string
    source_updated_at: string | null
    observed_at: string
    is_stale: boolean
    age_seconds: number
  }
}

export type MatchFiltersDto = {
  circuits: CircuitTier[]
  genders: Gender[]
  disciplines: Discipline[]
}
export type FacetCountsDto = {
  circuits: Record<CircuitTier, number>
  genders: Record<Gender, number>
  disciplines: Record<Discipline, number>
}
export type MatchCatalogDto = {
  status: 'live' | 'upcoming'
  matches: MatchDto[]
  filters: MatchFiltersDto
  facet_counts: FacetCountsDto
  featured_match_id: string | null
}

export type DataQualityDto = {
  capability: string
  status: CapabilityStatus
  provider: string
  reason: string | null
  observed_at: string
}
export type PointEventDto = {
  id: string
  match_id: string
  sequence: number
  set_number: number
  game_number: number
  point_number: number
  server_player_id: string | null
  winner_player_id: string | null
  score_before: MatchScoreDto | null
  score_after: MatchScoreDto
  is_break_point: boolean
  is_set_point: boolean
  is_match_point: boolean
  observed_at: string
  provider: string
  source_fingerprint: string
  revision: number
  quality: DataQualityDto | null
}
export type MatchStatisticDto = {
  match_id: string
  name: string
  period: string
  player1_value: number | null
  player2_value: number | null
  unit: string | null
  provenance: string
  availability: CapabilityStatus
  as_of: string
}
export type MomentumObservationDto = {
  match_id: string
  point_sequence: number
  state_version: number
  algorithm_version: string
  value: number
  leader_player_id: string | null
  is_provisional: boolean
  as_of: string
  input_summary: string
}
export type MatchSnapshotDto = {
  match: MatchDto
  points: PointEventDto[]
  statistics: MatchStatisticDto[]
  momentum: MomentumObservationDto[]
  quality: DataQualityDto[]
  state_version: number
  as_of: string
}
export type AnswerContextDto = {
  match_id: string
  state_version: number
  as_of: string
}
export type IntelligenceTopic = 'overview' | 'score' | 'statistics' | 'points' | 'momentum'
export type IntelligencePacketDto = {
  topic: IntelligenceTopic
  match_id: string
  state_version: number
  as_of: string
  status: MatchStatus
  players: [string, string]
  tournament: string
  round: string | null
  scheduled_at: string | null
  surface: string | null
  indoor: boolean | null
  format: string | null
  winner: string | null
  score: MatchScoreDto | null
  server: string | null
  statistics: Array<{
    name: string
    period: string
    player1_value: number | null
    player2_value: number | null
    unit: string | null
    provenance: string
    availability: CapabilityStatus
    as_of: string
  }>
  recent_points: Array<{
    sequence: number
    set_number: number
    game_number: number
    point_number: number
    server: string | null
    winner: string | null
    score_after: MatchScoreDto
    is_break_point: boolean
    is_set_point: boolean
    is_match_point: boolean
  }>
  momentum: Array<{
    point_sequence: number
    algorithm_version: string
    value: number
    leader: string | null
    is_provisional: boolean
    as_of: string
    input_summary: string
  }>
  key_points: Array<{
    sequence: number
    labels: string[]
    winner: string | null
  }>
  quality: Array<{
    capability: string
    status: CapabilityStatus
    reason: string | null
    observed_at: string
  }>
}
export type MatchStreamFrame =
  | {
      type: 'ready'
      id: string | null
      payload: { snapshot: MatchSnapshotDto; state_version: number; as_of: string }
    }
  | {
      type: 'match_delta'
      id: string | null
      payload: {
        match_id: string
        state_version: number | null
        as_of: string
        changes: string[]
        snapshot?: MatchSnapshotDto
        connection_status?: ConnectionStatus
      }
    }
  | {
      type: 'match_ended'
      id: string | null
      payload: { match_id: string; state_version: number | null; as_of: string }
    }
  | { type: 'heartbeat'; id: string | null; payload: Record<string, never> }
  | {
      type: 'error'
      id: string | null
      payload: { code: string; message: string; details: Record<string, unknown> }
    }
export type StructuredData = {
  kind: 'matches' | 'match' | 'intelligence' | 'unsupported'
  matches: MatchDto[]
  packet?: IntelligencePacketDto | null
  metadata?: Record<string, unknown>
  answer_context?: AnswerContextDto | null
}
export type ChatRequest = {
  scope: 'global' | 'match'
  match_id?: string
  messages: Array<{ role: 'user' | 'assistant'; content: string }>
}
export type ChatStatusPayload = {
  stage: string
  phase?: string
  completed?: number
  total?: number
  tool?: string | null
}
export type ChatWarning = {
  code: string
  message: string
  details: Record<string, unknown>
}
export type ChatEvent =
  | { type: 'status'; payload: ChatStatusPayload }
  | { type: 'data'; payload: StructuredData }
  | { type: 'text_delta'; payload: { delta: string } }
  | { type: 'done'; payload: { ok: boolean } }
  | { type: 'warning'; payload: ChatWarning }
  | { type: 'error'; payload: { code: string; message: string; details: Record<string, unknown> } }
