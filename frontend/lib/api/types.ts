export type MatchStatus = 'scheduled' | 'live' | 'finished' | 'cancelled' | 'postponed' | 'unknown'

export type PlayerDto = { id: string; name: string; country_code: string | null; ranking: number | null }
export type TournamentDto = { id: string; name: string; tour: string | null }
export type SetScoreDto = { number: number; player1_games: number | null; player2_games: number | null }
export type MatchScoreDto = {
  sets_won: [number, number]
  sets: SetScoreDto[]
  points: [string | null, string | null]
  is_tiebreak: boolean
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
  live_state: { score: MatchScoreDto | null; server_player_id: string | null } | null
  winner_player_id: string | null
  freshness: {
    provider: string
    source_updated_at: string | null
    observed_at: string
    is_stale: boolean
    age_seconds: number
  }
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
