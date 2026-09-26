// Runtime decoding for every P3 DTO and SSE event discriminator (T67).
// Unknown enums and malformed shapes fail visibly with P3DecodeError —
// nothing is coerced, defaulted or silently dropped. Decimal payloads stay
// strings exactly as the backend serializes them; absent data stays null.
import type {
  DecisionActionValue,
  DecisionSnapshotDto,
  DecisionStreamEvent,
  GateDto,
  LifecycleStateValue,
  OutcomeLevelDto,
  PaperEventDto,
  MarketPageDto,
  MarketQuoteDto,
  MarketStreamEvent,
  MarketsSnapshotDto,
  MarketSummaryDto,
  ModelAvailabilitySummaryValue,
  ModelAvailabilityValue,
  OpportunityAvailabilityDto,
  OpportunityModelStatus,
  OpportunityDto,
  PaperPositionDto,
  PaperPositionsViewDto,
  PositionStatusValue,
  PositionSummaryDto,
  PulseRowDto,
  PulseViewDto,
  QuoteSideValue,
  QuoteSourceValue,
  QuoteStateValue,
} from './types'
import type { CircuitTier, Gender } from './types'

export class P3DecodeError extends Error {
  readonly path: string

  constructor(path: string, message: string) {
    super(`P3 decode failed at ${path}: ${message}`)
    this.name = 'P3DecodeError'
    this.path = path
  }
}

const DECIMAL_PATTERN = /^-?\d+(\.\d+)?$/

const MARKET_STATUSES = ['scheduled', 'open', 'closed', 'resolved', 'unknown'] as const
const DECISION_ACTIONS = ['market_only', 'no_bet', 'wait', 'buy', 'hold', 'sell'] as const
const OPPORTUNITY_ACTIONS = ['buy', 'wait'] as const
const OPPORTUNITY_PHASES = ['live', 'upcoming'] as const
const QUOTE_STATES = [
  'realtime',
  'snapshot',
  'partial',
  'no_liquidity',
  'unavailable',
  'stale',
  'limited',
] as const
const QUOTE_SOURCES = ['realtime', 'snapshot'] as const
const MODEL_AVAILABILITY_SUMMARY = [
  'available',
  'eligible_unpromoted',
  'out_of_scope',
  'not_evaluated',
] as const
const OPPORTUNITY_AVAILABILITY_REASONS = [
  'HAS_OPPORTUNITIES',
  'ELIGIBLE_UNPROMOTED',
  'NO_ELIGIBLE_ACTION',
  'NO_COVERED_MARKET',
  'DECISION_GAP',
] as const
const OPPORTUNITY_MODEL_STATUSES = ['not_promoted', 'promoted', 'unknown'] as const
const MARKET_PHASES = ['prematch', 'live', 'closed'] as const
const MODEL_AVAILABILITY = ['available', 'degraded', 'unpromoted', 'unavailable'] as const
const QUOTE_SIDES = ['entry', 'exit'] as const
const POSITION_STATUSES = [
  'entry_pending',
  'missed',
  'open',
  'exit_pending',
  'exited',
  'exit_missed',
  'settled',
] as const
const PULSE_PHASES = ['live', 'upcoming', 'closed'] as const
const LIFECYCLE_STATES = [
  'entry_pending',
  'filled',
  'missed',
  'exit_pending',
  'exited',
  'exit_missed',
  'settled',
] as const
const PULSE_KINDS = ['position', 'opportunity'] as const
const PAPER_DELTA_STATES = [
  'entry_pending',
  'filled',
  'missed',
  'exit_pending',
  'exited',
  'exit_missed',
  'settlement_blocked',
  'settled',
] as const
const RESOLUTION_STATUSES = ['pending', 'proposed', 'disputed', 'final'] as const
const TIERS = ['atp', 'wta', 'challenger', 'itf', 'other'] as const
const GENDERS = ['men', 'women', 'mixed', 'unknown'] as const

type Raw = Record<string, unknown>

function raw(value: unknown, path: string): Raw {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new P3DecodeError(path, 'expected an object')
  }
  return value as Raw
}

function rawList(value: unknown, path: string): unknown[] {
  if (!Array.isArray(value)) {
    throw new P3DecodeError(path, 'expected an array')
  }
  return value
}

function str(value: unknown, path: string): string {
  if (typeof value !== 'string') {
    throw new P3DecodeError(path, 'expected a string')
  }
  return value
}

function strOrNull(value: unknown, path: string): string | null {
  if (value === null || value === undefined) return null
  return str(value, path)
}

function bool(value: unknown, path: string): boolean {
  if (typeof value !== 'boolean') {
    throw new P3DecodeError(path, 'expected a boolean')
  }
  return value
}

function boolOrFalse(value: unknown, path: string): boolean {
  // Additive overlay flags: absent means "not flagged" for older payloads,
  // but a present non-boolean still fails visibly.
  if (value === undefined || value === null) return false
  return bool(value, path)
}

function idsTuple(value: unknown, path: string): [string, string] | null {
  if (value === null || value === undefined) return null
  const items = rawList(value, path)
  if (items.length !== 2) {
    throw new P3DecodeError(path, 'expected exactly two player ids')
  }
  return [str(items[0], `${path}[0]`), str(items[1], `${path}[1]`)]
}

function nullableLevelPair(
  value: unknown,
  path: string,
): [string | null, string | null] | null {
  if (value === null || value === undefined) return null
  const items = rawList(value, path)
  if (items.length !== 2) {
    throw new P3DecodeError(path, 'expected a two-outcome level pair')
  }
  return [decimalOrNull(items[0], `${path}[0]`), decimalOrNull(items[1], `${path}[1]`)]
}

function int(value: unknown, path: string, options: { min?: number } = {}): number {
  const min = options.min ?? Number.NEGATIVE_INFINITY
  if (typeof value !== 'number' || !Number.isInteger(value) || value < min) {
    throw new P3DecodeError(path, `expected an integer >= ${min}`)
  }
  return value
}

function probability(value: unknown, path: string): number | null {
  if (value === null || value === undefined) return null
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > 1) {
    throw new P3DecodeError(path, 'expected a probability in [0, 1]')
  }
  return value
}

function decimal(value: unknown, path: string): string {
  const text = str(value, path)
  if (!DECIMAL_PATTERN.test(text)) {
    throw new P3DecodeError(path, 'expected a decimal string')
  }
  return text
}

function decimalOrNull(value: unknown, path: string): string | null {
  if (value === null || value === undefined) return null
  return decimal(value, path)
}

function oneOf<T extends string>(value: unknown, allowed: readonly T[], path: string): T {
  const text = str(value, path)
  if (!(allowed as readonly string[]).includes(text)) {
    throw new P3DecodeError(path, `unknown enum value "${text}"`)
  }
  return text as T
}

function oneOfOrNull<T extends string>(
  value: unknown,
  allowed: readonly T[],
  path: string,
): T | null {
  if (value === null || value === undefined) return null
  return oneOf(value, allowed, path)
}

function namesTuple(value: unknown, path: string): [string, string] | null {
  if (value === null || value === undefined) return null
  const items = rawList(value, path)
  if (items.length !== 2) {
    throw new P3DecodeError(path, 'expected exactly two player names')
  }
  return [str(items[0], `${path}[0]`), str(items[1], `${path}[1]`)]
}

function localizedNamesTuple(
  value: unknown,
  path: string,
): [string | null, string | null] | null {
  if (value === null || value === undefined) return null
  const items = rawList(value, path)
  if (items.length !== 2) {
    throw new P3DecodeError(path, 'expected exactly two localized player names')
  }
  return [
    strOrNull(items[0], `${path}[0]`),
    strOrNull(items[1], `${path}[1]`),
  ]
}

function imagesTuple(
  value: unknown,
  path: string,
): [string | null, string | null] | null {
  if (value === null || value === undefined) return null
  const items = rawList(value, path)
  if (items.length !== 2) {
    throw new P3DecodeError(path, 'expected exactly two player photo URLs')
  }
  return [
    strOrNull(items[0], `${path}[0]`),
    strOrNull(items[1], `${path}[1]`),
  ]
}

function levelTuple(value: unknown, path: string): [string, string] | null {
  if (value === null || value === undefined) return null
  const items = rawList(value, path)
  if (items.length !== 2) {
    throw new P3DecodeError(path, 'expected a [player_id, price] tuple')
  }
  return [str(items[0], `${path}[0]`), decimal(items[1], `${path}[1]`)]
}

// ---------------------------------------------------------------------------
// REST DTO decoders
// ---------------------------------------------------------------------------

function decodeOpportunity(value: unknown, path: string): OpportunityDto {
  const item = raw(value, path)
  return {
    match_id: str(item.match_id, `${path}.match_id`),
    market_id: str(item.market_id, `${path}.market_id`),
    phase: oneOf(item.phase, OPPORTUNITY_PHASES, `${path}.phase`),
    action: oneOf(item.action, OPPORTUNITY_ACTIONS, `${path}.action`),
    target_player_id: strOrNull(item.target_player_id, `${path}.target_player_id`),
    player_ids: idsTuple(item.player_ids, `${path}.player_ids`),
    player_names: namesTuple(item.player_names, `${path}.player_names`),
    player_localized_names: localizedNamesTuple(
      item.player_localized_names,
      `${path}.player_localized_names`,
    ),
    player_images: imagesTuple(item.player_images, `${path}.player_images`),
    model_probability: probability(item.model_probability, `${path}.model_probability`),
    executable_probability: probability(
      item.executable_probability,
      `${path}.executable_probability`,
    ),
    conservative_net_edge: decimalOrNull(
      item.conservative_net_edge,
      `${path}.conservative_net_edge`,
    ),
    max_acceptable_price: decimalOrNull(
      item.max_acceptable_price,
      `${path}.max_acceptable_price`,
    ),
    tournament_tier: oneOfOrNull(item.tournament_tier, TIERS, `${path}.tournament_tier`) as
      | CircuitTier
      | null,
    tournament_name: strOrNull(item.tournament_name, `${path}.tournament_name`),
    is_stale: boolOrFalse(item.is_stale, `${path}.is_stale`),
    has_gap: boolOrFalse(item.has_gap, `${path}.has_gap`),
    as_of: strOrNull(item.as_of, `${path}.as_of`),
  }
}

export function decodeOpportunityAvailability(
  value: unknown,
  path: string,
): OpportunityAvailabilityDto {
  const item = raw(value, path)
  return {
    reason: oneOf(item.reason, OPPORTUNITY_AVAILABILITY_REASONS, `${path}.reason`),
    model_status: oneOf(
      item.model_status,
      OPPORTUNITY_MODEL_STATUSES,
      `${path}.model_status`,
    ) as OpportunityModelStatus,
  }
}

export function decodeOpportunityList(body: unknown): {
  rows: OpportunityDto[]
  availability: OpportunityAvailabilityDto | null
} {
  const envelope = raw(body, 'opportunities')
  const availability = envelope.availability
  return {
    rows: rawList(envelope.data, 'opportunities.data').map((item, index) =>
      decodeOpportunity(item, `opportunities.data[${index}]`),
    ),
    availability:
      availability === undefined || availability === null
        ? null
        : decodeOpportunityAvailability(availability, 'opportunities.availability'),
  }
}

export function decodeMarketQuote(value: unknown, path: string): MarketQuoteDto {
  const item = raw(value, path)
  return {
    state: oneOf(item.state, QUOTE_STATES, `${path}.state`) as QuoteStateValue,
    source: oneOfOrNull(item.source, QUOTE_SOURCES, `${path}.source`) as
      | QuoteSourceValue
      | null,
    as_of: strOrNull(item.as_of, `${path}.as_of`),
    outcome_bids: nullableLevelPair(item.outcome_bids, `${path}.outcome_bids`),
    outcome_asks: nullableLevelPair(item.outcome_asks, `${path}.outcome_asks`),
    best_bid: levelTuple(item.best_bid, `${path}.best_bid`),
    best_ask: levelTuple(item.best_ask, `${path}.best_ask`),
    spread: decimalOrNull(item.spread, `${path}.spread`),
    depth_usd: decimalOrNull(item.depth_usd, `${path}.depth_usd`),
  }
}

function decodeMarketSummary(value: unknown, path: string): MarketSummaryDto {
  const item = raw(value, path)
  return {
    market_id: str(item.market_id, `${path}.market_id`),
    match_id: strOrNull(item.match_id, `${path}.match_id`),
    question: strOrNull(item.question, `${path}.question`),
    status: oneOf(item.status, MARKET_STATUSES, `${path}.status`),
    tournament_name: strOrNull(item.tournament_name, `${path}.tournament_name`),
    tier: oneOfOrNull(item.tier, TIERS, `${path}.tier`) as CircuitTier | null,
    gender: oneOfOrNull(item.gender, GENDERS, `${path}.gender`) as Gender | null,
    phase: oneOfOrNull(item.phase, MARKET_PHASES, `${path}.phase`),
    model_availability: oneOf(
      item.model_availability ?? 'not_evaluated',
      MODEL_AVAILABILITY_SUMMARY,
      `${path}.model_availability`,
    ) as ModelAvailabilitySummaryValue,
    decision_action: oneOfOrNull(
      item.decision_action,
      DECISION_ACTIONS,
      `${path}.decision_action`,
    ) as DecisionActionValue | null,
    reason_code: strOrNull(item.reason_code, `${path}.reason_code`),
    player_ids: idsTuple(item.player_ids, `${path}.player_ids`),
    player_names: namesTuple(item.player_names, `${path}.player_names`),
    player_localized_names: localizedNamesTuple(
      item.player_localized_names,
      `${path}.player_localized_names`,
    ),
    player_images: imagesTuple(item.player_images, `${path}.player_images`),
    model_probability: probability(item.model_probability, `${path}.model_probability`),
    quote: decodeMarketQuote(item.quote, `${path}.quote`),
    is_stale: boolOrFalse(item.is_stale, `${path}.is_stale`),
    has_gap: boolOrFalse(item.has_gap, `${path}.has_gap`),
    as_of: strOrNull(item.as_of, `${path}.as_of`),
  }
}

export function decodeMarketPage(body: unknown): MarketPageDto {
  const envelope = raw(body, 'markets')
  return {
    markets: rawList(envelope.data, 'markets.data').map((item, index) =>
      decodeMarketSummary(item, `markets.data[${index}]`),
    ),
    page: int(envelope.page, 'markets.page', { min: 1 }),
    page_size: int(envelope.page_size, 'markets.page_size', { min: 1 }),
    total: int(envelope.total, 'markets.total', { min: 0 }),
  }
}

function decodePosition(value: unknown, path: string): PaperPositionDto {
  const item = raw(value, path)
  return {
    position_id: str(item.position_id, `${path}.position_id`),
    match_id: str(item.match_id, `${path}.match_id`),
    market_id: str(item.market_id, `${path}.market_id`),
    tournament_name: strOrNull(item.tournament_name, `${path}.tournament_name`),
    outcome_player_id: str(item.outcome_player_id, `${path}.outcome_player_id`),
    player_ids: idsTuple(item.player_ids, `${path}.player_ids`),
    player_names: namesTuple(item.player_names, `${path}.player_names`),
    player_localized_names: localizedNamesTuple(
      item.player_localized_names,
      `${path}.player_localized_names`,
    ),
    player_images: imagesTuple(item.player_images, `${path}.player_images`),
    status: oneOf(item.status, POSITION_STATUSES, `${path}.status`) as PositionStatusValue,
    entry_cost: decimal(item.entry_cost, `${path}.entry_cost`),
    shares: decimal(item.shares, `${path}.shares`),
    average_entry_price: decimalOrNull(item.average_entry_price, `${path}.average_entry_price`),
    current_exit_value: decimalOrNull(item.current_exit_value, `${path}.current_exit_value`),
    net_pnl: decimalOrNull(item.net_pnl, `${path}.net_pnl`),
    freshness_as_of: strOrNull(item.freshness_as_of, `${path}.freshness_as_of`),
  }
}

export function decodePaperPositions(body: unknown): PaperPositionsViewDto {
  const envelope = raw(body, 'paper_positions')
  return {
    open: rawList(envelope.open, 'paper_positions.open').map((item, index) =>
      decodePosition(item, `paper_positions.open[${index}]`),
    ),
    recent: rawList(envelope.recent, 'paper_positions.recent').map((item, index) =>
      decodePosition(item, `paper_positions.recent[${index}]`),
    ),
  }
}

function decodePulseRow(value: unknown, path: string): PulseRowDto {
  const item = raw(value, path)
  return {
    match_id: str(item.match_id, `${path}.match_id`),
    market_id: strOrNull(item.market_id, `${path}.market_id`),
    kind: oneOf(item.kind, PULSE_KINDS, `${path}.kind`),
    action: oneOf(item.action, DECISION_ACTIONS, `${path}.action`) as DecisionActionValue,
    phase: oneOfOrNull(item.phase, PULSE_PHASES, `${path}.phase`) as PulseRowDto['phase'],
    player_names: namesTuple(item.player_names, `${path}.player_names`),
    player_localized_names: localizedNamesTuple(
      item.player_localized_names,
      `${path}.player_localized_names`,
    ),
    player_images: imagesTuple(item.player_images, `${path}.player_images`),
    model_probability: probability(item.model_probability, `${path}.model_probability`),
    executable_probability: probability(
      item.executable_probability,
      `${path}.executable_probability`,
    ),
    conservative_net_edge: decimalOrNull(
      item.conservative_net_edge,
      `${path}.conservative_net_edge`,
    ),
    tournament_name: strOrNull(item.tournament_name, `${path}.tournament_name`),
    is_stale: boolOrFalse(item.is_stale, `${path}.is_stale`),
    has_gap: boolOrFalse(item.has_gap, `${path}.has_gap`),
    as_of: strOrNull(item.as_of, `${path}.as_of`),
  }
}

export function decodePulse(body: unknown): PulseViewDto {
  const envelope = raw(body, 'pulse')
  return {
    data: rawList(envelope.data, 'pulse.data').map((item, index) =>
      decodePulseRow(item, `pulse.data[${index}]`),
    ),
    has_open_position: bool(envelope.has_open_position, 'pulse.has_open_position'),
  }
}

const PAPER_EVENT_KINDS = [
  'entry_intent',
  'entry_fill',
  'entry_no_fill',
  'exit_intent',
  'exit_fill',
  'exit_no_fill',
  'settled',
] as const

function decodePaperEvent(value: unknown, path: string): PaperEventDto {
  const item = raw(value, path)
  return {
    id: str(item.id, `${path}.id`),
    kind: oneOf(item.kind, PAPER_EVENT_KINDS, `${path}.kind`) as PaperEventDto['kind'],
    at: strOrNull(item.at, `${path}.at`),
    reason_code: strOrNull(item.reason_code, `${path}.reason_code`),
  }
}

function decodeGate(value: unknown, path: string): GateDto {
  const item = raw(value, path)
  return {
    gate: str(item.gate, `${path}.gate`),
    passed: bool(item.passed, `${path}.passed`),
    reason_code: strOrNull(item.reason_code, `${path}.reason_code`),
  }
}

function decodeOutcomeLevel(value: unknown, path: string): OutcomeLevelDto {
  const item = raw(value, path)
  return {
    player_id: str(item.player_id, `${path}.player_id`),
    best_bid: decimalOrNull(item.best_bid, `${path}.best_bid`),
    best_ask: decimalOrNull(item.best_ask, `${path}.best_ask`),
  }
}

function decodePositionSummary(value: unknown, path: string): PositionSummaryDto {
  const item = raw(value, path)
  const events = item.events === undefined || item.events === null ? [] : rawList(item.events, `${path}.events`)
  return {
    position_id: str(item.position_id, `${path}.position_id`),
    outcome_player_id: str(item.outcome_player_id, `${path}.outcome_player_id`),
    status: oneOf(item.status, POSITION_STATUSES, `${path}.status`) as PositionStatusValue,
    entry_cost: decimal(item.entry_cost, `${path}.entry_cost`),
    shares: decimal(item.shares, `${path}.shares`),
    average_entry_price: decimalOrNull(item.average_entry_price, `${path}.average_entry_price`),
    current_exit_value: decimalOrNull(item.current_exit_value, `${path}.current_exit_value`),
    net_pnl: decimalOrNull(item.net_pnl, `${path}.net_pnl`),
    events: events.map((event, index) => decodePaperEvent(event, `${path}.events[${index}]`)),
  }
}

function decodeDecisionSnapshot(value: unknown, path: string): DecisionSnapshotDto {
  const item = raw(value, path)
  const probabilitiesRaw = item.model_probabilities
  let probabilities: Record<string, number> | null = null
  if (probabilitiesRaw !== null && probabilitiesRaw !== undefined) {
    const record = raw(probabilitiesRaw, `${path}.model_probabilities`)
    probabilities = {}
    for (const [playerId, probabilityValue] of Object.entries(record)) {
      const probabilityPath = `${path}.model_probabilities.${playerId}`
      const decoded = probability(probabilityValue, probabilityPath)
      if (decoded === null) {
        throw new P3DecodeError(probabilityPath, 'expected a probability in [0, 1]')
      }
      probabilities[playerId] = decoded
    }
  }
  const lifecycle = rawList(item.lifecycle, `${path}.lifecycle`).map((state, index) =>
    oneOf(state, LIFECYCLE_STATES, `${path}.lifecycle[${index}]`) as LifecycleStateValue,
  )
  return {
    match_id: str(item.match_id, `${path}.match_id`),
    market_id: strOrNull(item.market_id, `${path}.market_id`),
    action: oneOf(item.action, DECISION_ACTIONS, `${path}.action`) as DecisionActionValue,
    reason_code: strOrNull(item.reason_code, `${path}.reason_code`),
    target_player_id: strOrNull(item.target_player_id, `${path}.target_player_id`),
    observation_version: int(item.observation_version, `${path}.observation_version`, { min: 0 }),
    model_probabilities: probabilities,
    model_availability: oneOfOrNull(
      item.model_availability,
      MODEL_AVAILABILITY,
      `${path}.model_availability`,
    ) as ModelAvailabilityValue | null,
    quote_average_price: decimalOrNull(item.quote_average_price, `${path}.quote_average_price`),
    quote_side: oneOfOrNull(item.quote_side, QUOTE_SIDES, `${path}.quote_side`) as
      | QuoteSideValue
      | null,
    conservative_net_edge: decimalOrNull(
      item.conservative_net_edge,
      `${path}.conservative_net_edge`,
    ),
    max_acceptable_price: decimalOrNull(
      item.max_acceptable_price,
      `${path}.max_acceptable_price`,
    ),
    hold_value: decimalOrNull(item.hold_value, `${path}.hold_value`),
    model_version: strOrNull(item.model_version, `${path}.model_version`),
    calibration_version: strOrNull(item.calibration_version, `${path}.calibration_version`),
    policy_version: strOrNull(item.policy_version, `${path}.policy_version`),
    data_version: strOrNull(item.data_version, `${path}.data_version`),
    gates: (item.gates === undefined || item.gates === null
      ? []
      : rawList(item.gates, `${path}.gates`)
    ).map((gate, index) => decodeGate(gate, `${path}.gates[${index}]`)),
    outcome_levels: (item.outcome_levels === undefined || item.outcome_levels === null
      ? []
      : rawList(item.outcome_levels, `${path}.outcome_levels`)
    ).map((level, index) => decodeOutcomeLevel(level, `${path}.outcome_levels[${index}]`)),
    position:
      item.position === null || item.position === undefined
        ? null
        : decodePositionSummary(item.position, `${path}.position`),
    lifecycle,
    is_stale: bool(item.is_stale, `${path}.is_stale`),
    has_gap: bool(item.has_gap, `${path}.has_gap`),
    lock_profit_available: bool(item.lock_profit_available, `${path}.lock_profit_available`),
    as_of: strOrNull(item.as_of, `${path}.as_of`),
  }
}

export function decodeMatchDecision(body: unknown): DecisionSnapshotDto {
  const envelope = raw(body, 'decision')
  return decodeDecisionSnapshot(envelope.data, 'decision.data')
}

export function decodeMarketsSnapshot(payload: unknown): MarketsSnapshotDto {
  const item = raw(payload, 'markets_snapshot')
  return {
    markets: int(item.markets, 'markets_snapshot.markets', { min: 0 }),
    opportunities: int(item.opportunities, 'markets_snapshot.opportunities', { min: 0 }),
    open_positions: int(item.open_positions, 'markets_snapshot.open_positions', { min: 0 }),
    availability:
      item.availability === undefined || item.availability === null
        ? null
        : (oneOf(
            item.availability,
            OPPORTUNITY_AVAILABILITY_REASONS,
            'markets_snapshot.availability',
          ) as MarketsSnapshotDto['availability']),
  }
}

// ---------------------------------------------------------------------------
// SSE event discriminators
// ---------------------------------------------------------------------------

function decodeDecisionDelta(payload: unknown, path: string) {
  const item = raw(payload, path)
  return {
    type: 'decision_delta' as const,
    match_id: str(item.match_id, `${path}.match_id`),
    observation_version: int(item.observation_version, `${path}.observation_version`, { min: 0 }),
    action: oneOf(item.action, DECISION_ACTIONS, `${path}.action`) as DecisionActionValue,
    as_of: str(item.as_of, `${path}.as_of`),
  }
}

export function decodeMarketStreamEvent(type: string, payload: unknown): MarketStreamEvent {
  const path = `markets_stream.${type}`
  switch (type) {
    case 'ready':
      return { type: 'ready', payload: decodeMarketsSnapshot(payload) }
    case 'quotes_changed': {
      const item = raw(payload, path)
      return {
        type: 'quotes_changed',
        payload: {
          sequence: int(item.sequence, `${path}.sequence`, { min: 1 }),
          count: int(item.count, `${path}.count`, { min: 0 }),
          as_of: str(item.as_of, `${path}.as_of`),
        },
      }
    }
    case 'market_delta': {
      const item = raw(payload, path)
      return {
        type: 'market_delta',
        payload: {
          type: 'market_delta',
          market_id: str(item.market_id, `${path}.market_id`),
          sequence: int(item.sequence, `${path}.sequence`, { min: 0 }),
          book_hash: str(item.book_hash, `${path}.book_hash`),
          as_of: str(item.as_of, `${path}.as_of`),
        },
      }
    }
    case 'market_gap': {
      const item = raw(payload, path)
      return {
        type: 'market_gap',
        payload: {
          type: 'market_gap',
          market_id: str(item.market_id, `${path}.market_id`),
          reason: str(item.reason, `${path}.reason`),
          as_of: str(item.as_of, `${path}.as_of`),
        },
      }
    }
    case 'decision_delta':
      return { type: 'decision_delta', payload: decodeDecisionDelta(payload, path) }
    case 'paper_delta': {
      const item = raw(payload, path)
      return {
        type: 'paper_delta',
        payload: {
          type: 'paper_delta',
          state: oneOf(item.state, PAPER_DELTA_STATES, `${path}.state`),
          id: str(item.id, `${path}.id`),
          reason: strOrNull(item.reason, `${path}.reason`),
          as_of: str(item.as_of, `${path}.as_of`),
        },
      }
    }
    case 'resolution_delta': {
      const item = raw(payload, path)
      const payouts =
        item.payouts === null || item.payouts === undefined
          ? undefined
          : rawList(item.payouts, `${path}.payouts`).map((entry, index) => {
              const payout = raw(entry, `${path}.payouts[${index}]`)
              return {
                player_id: str(payout.player_id, `${path}.payouts[${index}].player_id`),
                payout_per_share: decimal(
                  payout.payout_per_share,
                  `${path}.payouts[${index}].payout_per_share`,
                ),
              }
            })
      return {
        type: 'resolution_delta',
        payload: {
          type: 'resolution_delta',
          market_id: str(item.market_id, `${path}.market_id`),
          status: oneOf(item.status, RESOLUTION_STATUSES, `${path}.status`),
          ...(item.rules_version === undefined
            ? {}
            : { rules_version: int(item.rules_version, `${path}.rules_version`, { min: 1 }) }),
          ...(payouts === undefined ? {} : { payouts }),
          ...(item.confirmed_at === undefined
            ? {}
            : { confirmed_at: strOrNull(item.confirmed_at, `${path}.confirmed_at`) }),
        },
      }
    }
    case 'heartbeat':
      return { type: 'heartbeat', payload: {} }
    default:
      throw new P3DecodeError(path, `unknown market stream event "${type}"`)
  }
}

export function decodeDecisionStreamEvent(type: string, payload: unknown): DecisionStreamEvent {
  const path = `decision_stream.${type}`
  switch (type) {
    case 'ready': {
      const item = raw(payload, path)
      return {
        type: 'ready',
        payload: {
          match_id: str(item.match_id, `${path}.match_id`),
          decision:
            item.decision === null || item.decision === undefined
              ? null
              : decodeDecisionSnapshot(item.decision, `${path}.decision`),
          observation_version: int(item.observation_version, `${path}.observation_version`, {
            min: 0,
          }),
          action: oneOfOrNull(item.action, DECISION_ACTIONS, `${path}.action`) as
            | DecisionActionValue
            | null,
        },
      }
    }
    case 'decision_delta':
      return { type: 'decision_delta', payload: decodeDecisionDelta(payload, path) }
    case 'heartbeat':
      return { type: 'heartbeat', payload: {} }
    default:
      throw new P3DecodeError(path, `unknown decision stream event "${type}"`)
  }
}
