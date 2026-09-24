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

export type PlayerDto = {
  id: string
  name: string
  country_code: string | null
  country_alpha2?: string | null
  ranking: number | null
  localized_name?: string | null
}
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
  sets_won: [number, number] | null
  sets: SetScoreDto[]
  points: [string | null, string | null]
  is_tiebreak: boolean | null
}
export type LiveStateDto = {
  current_set_number?: number | null
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
  is_break_point: boolean | null
  is_set_point: boolean | null
  is_match_point: boolean | null
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
    is_break_point: boolean | null
    is_set_point: boolean | null
    is_match_point: boolean | null
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
export type PlayerResolutionCandidateDto = {
  player: PlayerSummaryDto
  matched_alias: string
  alias_kind: string
  current_rank: number | null
}
export type PlayerResolutionDto = {
  status: 'resolved' | 'ambiguous' | 'not_found'
  query: string
  player: PlayerSummaryDto | null
  candidates: PlayerResolutionCandidateDto[]
}
export type PlayerHistoryContextDto = {
  player: PlayerDto
  scope: 'yesterday' | 'last' | 'recent' | 'season'
  season: number | null
  availability: CapabilityStatus
  season_record: PlayerSeasonRecordDto | null
  empty_reason: 'no_results_in_scope' | 'season_record_unavailable' | null
}
export type StructuredData = {
  kind:
    | 'matches'
    | 'match'
    | 'intelligence'
    | 'player_resolution'
    | 'player_history'
    | 'market_opportunities'
    | 'match_decision'
    | 'unsupported'
  matches: MatchDto[]
  packet?: IntelligencePacketDto | null
  resolution?: PlayerResolutionDto | null
  player_history?: PlayerHistoryContextDto | null
  market_opportunities?: { opportunities: OpportunityDto[]; truncated: boolean } | null
  match_decision?: DecisionSnapshotDto | null
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

// ---------------------------------------------------------------------------
// P2.6 player directory DTOs (backend /api/v1/players/*)
// ---------------------------------------------------------------------------

export type PlayerSummaryDto = {
  id: string
  name: string
  localized_name: string | null
  country_code: string | null
  country_alpha2?: string | null
  ranking: number | null
}

export type RankingEntryDto = {
  player: PlayerSummaryDto
  tour: 'ATP' | 'WTA'
  rank: number
  points: number
  movement: 'up' | 'down' | 'same' | 'unknown'
  ranking_date: string
  fetched_at: string
}

export type RankingPageDto = {
  tour: 'ATP' | 'WTA'
  page: number
  page_size: number
  total: number
  entries: RankingEntryDto[]
  as_of: string | null
  availability: CapabilityStatus
}

/** REST `/api/players/search` resolution envelope (nested domain shape). */
export type PlayerSearchCandidateDto = {
  player: PlayerSummaryDto
  matched_alias: string
  alias_kind: string
  current_rank: number | null
}

export type PlayerSearchResolutionDto = {
  status: 'resolved' | 'ambiguous' | 'not_found'
  query: string
  player: PlayerSummaryDto | null
  candidates: PlayerSearchCandidateDto[]
}

export type SurfaceRecordDto = { won: number | null; lost: number | null }

export type PlayerSeasonRecordDto = {
  season: number
  matches_won: number | null
  matches_lost: number | null
  titles: number | null
  hard: SurfaceRecordDto | null
  clay: SurfaceRecordDto | null
  grass: SurfaceRecordDto | null
}

export type PlayerProfileDataDto = {
  player: PlayerSummaryDto
  birth_date: string | null
  image_url: string | null
  seasons: PlayerSeasonRecordDto[]
}

export type PlayerProfileViewDto = {
  profile: PlayerProfileDataDto
  ranking: RankingEntryDto | null
  selected_season: number
  season_record: PlayerSeasonRecordDto | null
  current_match: MatchDto | null
}

export type PlayerResultPageDto = {
  player: PlayerSummaryDto
  season: number
  tiers: CircuitTier[]
  outcome: 'all' | 'won' | 'lost'
  page: number
  page_size: number
  total: number
  matches: MatchDto[]
  availability: CapabilityStatus
}

// ---------------------------------------------------------------------------
// P3 market decision support DTOs (T67). Mirror the backend public schemas:
// internal IDs only, decimals as strings, canonical enums.
// ---------------------------------------------------------------------------

export type MarketPhase = 'prematch' | 'live' | 'closed'
export type MarketStatusValue = 'scheduled' | 'open' | 'closed' | 'resolved' | 'unknown'
export type DecisionActionValue = 'market_only' | 'no_bet' | 'wait' | 'buy' | 'hold' | 'sell'
export type OpportunityActionValue = 'buy' | 'wait'
export type OpportunityPhaseValue = 'live' | 'upcoming'
export type ModelAvailabilityValue = 'available' | 'degraded' | 'unpromoted' | 'unavailable'
export type QuoteSideValue = 'entry' | 'exit'
export type PositionStatusValue =
  | 'entry_pending'
  | 'missed'
  | 'open'
  | 'exit_pending'
  | 'exited'
  | 'exit_missed'
  | 'settled'
export type LifecycleStateValue =
  | 'entry_pending'
  | 'filled'
  | 'missed'
  | 'exit_pending'
  | 'exited'
  | 'exit_missed'
  | 'settled'
export type PulseKindValue = 'position' | 'opportunity'
export type PaperDeltaStateValue =
  | 'entry_pending'
  | 'filled'
  | 'missed'
  | 'exit_pending'
  | 'exited'
  | 'exit_missed'
  | 'settlement_blocked'
  | 'settled'
export type ResolutionStatusValue = 'pending' | 'proposed' | 'disputed' | 'final'

export type OpportunityDto = {
  match_id: string
  market_id: string
  phase: OpportunityPhaseValue
  action: OpportunityActionValue
  target_player_id: string | null
  player_ids: [string, string] | null
  player_names: [string, string] | null
  model_probability: number | null
  executable_probability: number | null
  conservative_net_edge: string | null
  max_acceptable_price: string | null
  tournament_tier: CircuitTier | null
  tournament_name: string | null
  is_stale: boolean
  has_gap: boolean
  as_of: string | null
}

export type QuoteStateValue =
  | 'realtime'
  | 'snapshot'
  | 'partial'
  | 'no_liquidity'
  | 'unavailable'
  | 'stale'
  | 'limited'
export type QuoteSourceValue = 'realtime' | 'snapshot'
/** Explicit per-market model availability. Never inferred from a null action. */
export type ModelAvailabilitySummaryValue =
  | 'available'
  | 'eligible_unpromoted'
  | 'out_of_scope'
  | 'not_evaluated'
export type OpportunityAvailabilityReason =
  | 'HAS_OPPORTUNITIES'
  | 'ELIGIBLE_UNPROMOTED'
  | 'NO_ELIGIBLE_ACTION'
  | 'NO_COVERED_MARKET'
  | 'DECISION_GAP'
export type OpportunityModelStatus = 'not_promoted' | 'promoted' | 'unknown'

export type MarketQuoteDto = {
  state: QuoteStateValue
  source: QuoteSourceValue | null
  as_of: string | null
  outcome_bids: [string | null, string | null] | null
  outcome_asks: [string | null, string | null] | null
  best_bid: [string, string] | null
  best_ask: [string, string] | null
  spread: string | null
  depth_usd: string | null
}

export type OpportunityAvailabilityDto = {
  reason: OpportunityAvailabilityReason
  model_status: OpportunityModelStatus
}

export type MarketSummaryDto = {
  market_id: string
  match_id: string | null
  question: string | null
  status: MarketStatusValue
  tournament_name: string | null
  tier: CircuitTier | null
  gender: Gender | null
  phase: MarketPhase | null
  model_availability: ModelAvailabilitySummaryValue
  decision_action: DecisionActionValue | null
  reason_code: string | null
  player_ids: [string, string] | null
  player_names: [string, string] | null
  model_probability: number | null
  quote: MarketQuoteDto
  is_stale: boolean
  has_gap: boolean
  as_of: string | null
}

export type MarketPageDto = {
  markets: MarketSummaryDto[]
  page: number
  page_size: number
  total: number
}

export type PaperPositionDto = {
  position_id: string
  match_id: string
  market_id: string
  tournament_name: string | null
  outcome_player_id: string
  player_ids: [string, string] | null
  player_names: [string, string] | null
  status: PositionStatusValue
  entry_cost: string
  shares: string
  average_entry_price: string | null
  current_exit_value: string | null
  net_pnl: string | null
  freshness_as_of: string | null
}

export type PaperPositionsViewDto = {
  open: PaperPositionDto[]
  recent: PaperPositionDto[]
}

export type PulseRowDto = {
  match_id: string
  market_id: string | null
  kind: PulseKindValue
  action: DecisionActionValue
  phase: OpportunityPhaseValue | 'closed' | null
  player_names: [string, string] | null
  model_probability: number | null
  executable_probability: number | null
  conservative_net_edge: string | null
  tournament_name: string | null
  is_stale: boolean
  has_gap: boolean
  as_of: string | null
}

export type PulseViewDto = {
  data: PulseRowDto[]
  has_open_position: boolean
}

export type PositionSummaryDto = {
  position_id: string
  outcome_player_id: string
  status: PositionStatusValue
  entry_cost: string
  shares: string
  average_entry_price: string | null
  current_exit_value: string | null
  net_pnl: string | null
  events: PaperEventDto[]
}

export type PaperEventKindValue =
  | 'entry_intent'
  | 'entry_fill'
  | 'entry_no_fill'
  | 'exit_intent'
  | 'exit_fill'
  | 'exit_no_fill'
  | 'settled'

export type PaperEventDto = {
  id: string
  kind: PaperEventKindValue
  at: string | null
  reason_code: string | null
}

export type GateDto = {
  gate: string
  passed: boolean
  reason_code: string | null
}

export type OutcomeLevelDto = {
  player_id: string
  best_bid: string | null
  best_ask: string | null
}

export type DecisionSnapshotDto = {
  match_id: string
  market_id: string | null
  action: DecisionActionValue
  reason_code: string | null
  target_player_id: string | null
  observation_version: number
  model_probabilities: Record<string, number> | null
  model_availability: ModelAvailabilityValue | null
  quote_average_price: string | null
  quote_side: QuoteSideValue | null
  conservative_net_edge: string | null
  max_acceptable_price: string | null
  hold_value: string | null
  model_version: string | null
  calibration_version: string | null
  policy_version: string | null
  data_version: string | null
  gates: GateDto[]
  outcome_levels: OutcomeLevelDto[]
  position: PositionSummaryDto | null
  lifecycle: LifecycleStateValue[]
  is_stale: boolean
  has_gap: boolean
  lock_profit_available: boolean
  as_of: string | null
}

export type MarketsSnapshotDto = {
  markets: number
  opportunities: number
  open_positions: number
  availability: OpportunityAvailabilityReason | null
}

// --- P3 SSE events ---------------------------------------------------------

export type MarketDeltaDto = {
  type: 'market_delta'
  market_id: string
  sequence: number
  book_hash: string
  as_of: string
}

export type MarketGapEventDto = {
  type: 'market_gap'
  market_id: string
  reason: string
  as_of: string
}

export type DecisionDeltaDto = {
  type: 'decision_delta'
  match_id: string
  observation_version: number
  action: DecisionActionValue
  as_of: string
}

export type PaperDeltaDto = {
  type: 'paper_delta'
  state: PaperDeltaStateValue
  id: string
  reason: string | null
  as_of: string
}

export type ResolutionPayoutDto = {
  player_id: string
  payout_per_share: string
}

export type ResolutionDeltaDto = {
  type: 'resolution_delta'
  market_id: string
  status: ResolutionStatusValue
  rules_version?: number
  payouts?: ResolutionPayoutDto[]
  confirmed_at?: string | null
}
export type QuoteCatalogChangedDto = {
  sequence: number
  count: number
  as_of: string
}

export type MarketStreamReadyEvent = { type: 'ready'; payload: MarketsSnapshotDto }
export type MarketStreamHeartbeatEvent = { type: 'heartbeat'; payload: Record<string, never> }
export type MalformedStreamEvent = { type: 'malformed'; payload: { reason: string } }
export type MarketStreamDeltaEvent =
  | { type: 'quotes_changed'; payload: QuoteCatalogChangedDto }
  | { type: 'market_delta'; payload: MarketDeltaDto }
  | { type: 'market_gap'; payload: MarketGapEventDto }
  | { type: 'decision_delta'; payload: DecisionDeltaDto }
  | { type: 'paper_delta'; payload: PaperDeltaDto }
  | { type: 'resolution_delta'; payload: ResolutionDeltaDto }
export type MarketStreamEvent =
  | MarketStreamReadyEvent
  | MarketStreamDeltaEvent
  | MarketStreamHeartbeatEvent
  | MalformedStreamEvent

export type DecisionStreamReadyEvent = {
  type: 'ready'
  payload: {
    match_id: string
    decision: DecisionSnapshotDto | null
    observation_version: number
    action: DecisionActionValue | null
  }
}
export type DecisionStreamDeltaEvent = { type: 'decision_delta'; payload: DecisionDeltaDto }
export type DecisionStreamEvent =
  | DecisionStreamReadyEvent
  | DecisionStreamDeltaEvent
  | { type: 'heartbeat'; payload: Record<string, never> }
  | MalformedStreamEvent
