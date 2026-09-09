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
export type StructuredData = { kind: 'matches' | 'match' | 'unsupported'; matches: MatchDto[] }
export type ChatRequest = {
  scope: 'global' | 'match'
  match_id?: string
  messages: Array<{ role: 'user' | 'assistant'; content: string }>
}
export type ChatEvent =
  | { type: 'status'; payload: { stage: string } }
  | { type: 'data'; payload: StructuredData }
  | { type: 'text_delta'; payload: { delta: string } }
  | { type: 'done'; payload: { ok: boolean } }
  | { type: 'error'; payload: { code: string; message: string; details: Record<string, unknown> } }
