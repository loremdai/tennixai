// Production P3 view models (T68): map canonical backend DTOs onto the
// frozen v0 row shapes. Presentation-only: every number/edge/action comes
// from the server; nothing here derives probability, edge, fills or
// settlement. Decimal strings are parsed for display formatting only, and
// absent values stay null so rows render an honest '—'.
import type {
  DecisionSnapshotDto,
  DecisionActionValue,
  MarketSummaryDto,
  ModelAvailabilitySummaryValue,
  OpportunityDto,
  PaperPositionDto,
  PulseRowDto,
  QuoteSourceValue,
  QuoteStateValue,
} from '@/lib/api/types'
import type { DecisionOverlay, DecisionState } from '@/components/p3/p3-preview-data'

export type RowPhase = 'live' | 'upcoming' | 'closed'

export type OpportunityRowModel = {
  id: string
  match: string
  tournament: string
  phase: Exclude<RowPhase, 'closed'>
  selection: string
  modelProbability: number | null
  executableProbability: number | null
  edgePp: number | null
  state: 'buy' | 'wait'
  maxBuyPrice: number | null
  freshness: string
  stale: boolean
  overlay: DecisionOverlay
  href: string
}

export type MarketRowModel = {
  id: string
  match: string
  tournament: string
  tier: string
  tierLabel: string
  gender: string
  phase: RowPhase
  /** Explicit model availability; never inferred from a decision action. */
  modelAvailability: ModelAvailabilitySummaryValue
  modelAvailabilityLabel: string | null
  /** Only a real decision observation sets this; null is not MARKET_ONLY. */
  decisionAction: DecisionActionValue | null
  quoteState: QuoteStateValue
  quoteSource: QuoteSourceValue | null
  quoteLabel: string
  playerOne: string
  playerTwo: string
  playerOneAsk: number | null
  playerTwoAsk: number | null
  spread: number | null
  depth: number | null
  modelProbability: number | null
  reason: string | null
  freshness: string
  stale: boolean
  overlay: DecisionOverlay
  href: string | null
}

export type PaperRowModel = {
  id: string
  match: string
  tournament: string
  direction: string
  state: 'entry_pending' | 'hold' | 'exit_pending' | 'exit_missed' | 'exited' | 'missed' | 'settled'
  cost: number
  shares: number
  averageEntry: number | null
  currentExitValue: number | null
  netPnl: number | null
  freshness: string
  detail: string
  href: string
}

export type PulseRowModel = {
  id: string
  priority: 'position' | 'sell' | 'buy_live' | 'buy_upcoming' | 'wait'
  match: string
  tournament: string
  phase: '直播' | '即将开始' | '已完赛'
  modelProbability: number | null
  executableProbability: number | null
  edgePp: number | null
  state: DecisionState
  freshness: string
  stale: boolean
  overlay: DecisionOverlay
  href: string
}

export const TIER_LABELS: Record<string, string> = {
  main: 'ATP/WTA 主巡',
  atp: 'ATP',
  wta: 'WTA',
  challenger: '挑战赛',
  itf: 'ITF 巡回赛',
  other: '其他比赛',
}

const REASON_LABELS: Record<string, string> = {
  MARKET_UNMAPPED: '暂时无法确认对应的比赛，仅显示市场报价',
  MODEL_UNPROMOTED: '模型仍在验证，目前仅显示市场报价',
  PROMOTION_NOT_GRANTED: '模型仍在验证，目前仅显示市场报价',
  ARTIFACT_INVALID: '目前仅显示市场报价',
  POLICY_DISABLED: '目前仅显示市场报价',
  OUT_OF_DOMAIN: '目前仅显示市场报价',
  DATA_INCOMPLETE: '比赛数据不完整，暂不提供判断',
  MODEL_DISAGREEMENT: '模型判断不一致，暂不提供建议',
  RULE_CHANGED: '评估标准更新，暂不提供判断',
  STALE: '市场报价更新较慢，相关判断已暂停',
  GAP: '比赛数据更新中断，相关判断已暂停',
  INSUFFICIENT_LIQUIDITY: '可交易金额不足',
  NO_NET_EDGE: '模型与市场的差距暂不明显',
}

/** Visible quote states (spec §5.3). A bare '—' is never a state. */
const QUOTE_STATE_LABELS: Record<QuoteStateValue, string> = {
  realtime: '实时更新',
  snapshot: '最近报价',
  partial: '部分报价',
  no_liquidity: '暂无可交易报价',
  unavailable: '报价暂不可用',
  stale: '上次有效报价',
  limited: '报价暂不可用',
}

/** Only these two carry a meaningful "· N 分钟前" suffix. */
const TIME_AWARE_QUOTE_STATES: QuoteStateValue[] = ['snapshot', 'partial']

/**
 * Model availability copy. `out_of_scope` deliberately returns null: low-tier
 * markets show their real quotes without any "model not covered" label.
 */
const MODEL_AVAILABILITY_LABELS: Record<
  ModelAvailabilitySummaryValue,
  string | null
> = {
  available: '已纳入模型评估',
  eligible_unpromoted: '模型仍在验证',
  out_of_scope: null,
  not_evaluated: '等待下一次评估',
}

export function quoteStateLabel(
  state: QuoteStateValue,
  asOf: string | null,
  now: Date,
): string {
  const base = QUOTE_STATE_LABELS[state]
  if (!TIME_AWARE_QUOTE_STATES.includes(state) || !asOf) return base
  return `${base} · ${formatFreshness(asOf, now)}`
}

const PAPER_DETAIL_LABELS: Record<PaperRowModel['state'], string> = {
  entry_pending: '正在确认模拟买入',
  hold: '已模拟买入，持有中',
  exit_pending: '正在确认模拟退出',
  exit_missed: '模拟退出未成交，仍持有至结算',
  exited: '模拟退出已完成',
  missed: '模拟买入未成交',
  settled: '比赛市场已结算',
}

export function parseDecimalOrNull(value: string | null | undefined): number | null {
  if (value === null || value === undefined) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

export function overlayOf(isStale: boolean, hasGap: boolean): DecisionOverlay {
  if (isStale) return 'stale'
  if (hasGap) return 'gap'
  return 'none'
}

/** Deterministic relative freshness text; `now` is injected for tests. */
export function formatFreshness(asOf: string | null, now: Date, stale = false): string {
  const prefix = stale ? '上次有效报价 · ' : ''
  if (!asOf) return `${prefix}时间未知`
  const then = new Date(asOf).getTime()
  if (!Number.isFinite(then)) return `${prefix}时间未知`
  const seconds = Math.max(0, Math.floor((now.getTime() - then) / 1000))
  if (seconds < 5) return `${prefix}刚刚`
  if (seconds < 60) return `${prefix}${seconds} 秒前`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${prefix}${minutes} 分前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${prefix}${hours} 小时前`
  return `${prefix}${Math.floor(hours / 24)} 天前`
}

function namesOf(dto: {
  player_names: [string, string] | null
}): [string, string] {
  return dto.player_names ?? ['—', '—']
}

export function toOpportunityRow(dto: OpportunityDto, now: Date): OpportunityRowModel {
  const [one, two] = namesOf(dto)
  let selection = '—'
  if (dto.target_player_id && dto.player_ids && dto.player_names) {
    const index = dto.player_ids.indexOf(dto.target_player_id)
    if (index >= 0) selection = dto.player_names[index]
  }
  return {
    id: dto.match_id,
    match: `${one} vs. ${two}`,
    tournament: dto.tournament_name ?? '—',
    phase: dto.phase,
    selection,
    modelProbability: dto.model_probability,
    executableProbability: dto.executable_probability,
    edgePp:
      dto.conservative_net_edge === null
        ? null
        : parseDecimalOrNull(dto.conservative_net_edge) === null
          ? null
          : (parseDecimalOrNull(dto.conservative_net_edge) as number) * 100,
    state: dto.action,
    maxBuyPrice: parseDecimalOrNull(dto.max_acceptable_price),
    freshness: formatFreshness(dto.as_of, now, dto.is_stale || dto.has_gap),
    stale: dto.is_stale,
    overlay: overlayOf(dto.is_stale, dto.has_gap),
    href: `/matches/${encodeURIComponent(dto.match_id)}`,
  }
}

export function toMarketRow(dto: MarketSummaryDto, now: Date): MarketRowModel {
  const [one, two] = namesOf(dto)
  const tier = dto.tier ?? 'other'
  const phase: RowPhase =
    dto.phase === 'live' ? 'live' : dto.phase === 'prematch' ? 'upcoming' : 'closed'
  return {
    id: dto.market_id,
    match: dto.match_id ? `${one} vs. ${two}` : (dto.question ?? '—'),
    tournament: dto.tournament_name ?? '—',
    tier,
    tierLabel: TIER_LABELS[tier] ?? tier,
    gender: dto.gender ?? 'unknown',
    phase,
    modelAvailability: dto.model_availability,
    modelAvailabilityLabel: MODEL_AVAILABILITY_LABELS[dto.model_availability],
    decisionAction: dto.decision_action,
    quoteState: dto.quote.state,
    quoteSource: dto.quote.source,
    quoteLabel: quoteStateLabel(dto.quote.state, dto.quote.as_of, now),
    playerOne: one,
    playerTwo: two,
    playerOneAsk: dto.quote.outcome_asks
      ? parseDecimalOrNull(dto.quote.outcome_asks[0])
      : null,
    playerTwoAsk: dto.quote.outcome_asks
      ? parseDecimalOrNull(dto.quote.outcome_asks[1])
      : null,
    spread: parseDecimalOrNull(dto.quote.spread),
    depth: parseDecimalOrNull(dto.quote.depth_usd),
    modelProbability: dto.model_probability,
    reason:
      dto.reason_code !== null
        ? (REASON_LABELS[dto.reason_code] ?? dto.reason_code)
        : null,
    freshness: formatFreshness(dto.quote.as_of, now, dto.quote.state === 'stale'),
    stale: dto.quote.state === 'stale',
    overlay: overlayOf(dto.is_stale, dto.has_gap),
    href: dto.match_id ? `/matches/${encodeURIComponent(dto.match_id)}` : null,
  }
}

const PAPER_STATE_MAP: Record<PaperPositionDto['status'], PaperRowModel['state']> = {
  entry_pending: 'entry_pending',
  missed: 'missed',
  open: 'hold',
  exit_pending: 'exit_pending',
  exited: 'exited',
  exit_missed: 'exit_missed',
  settled: 'settled',
}

export function toPaperRow(
  dto: PaperPositionDto,
  matchLabel: string | null,
  now: Date,
): PaperRowModel {
  const state = PAPER_STATE_MAP[dto.status]
  let direction = '—'
  if (dto.player_ids && dto.player_names) {
    const index = dto.player_ids.indexOf(dto.outcome_player_id)
    if (index >= 0) direction = dto.player_names[index]
  }
  return {
    id: dto.position_id,
    match: matchLabel ?? '—',
    tournament: dto.tournament_name ?? '—',
    direction,
    state,
    cost: parseDecimalOrNull(dto.entry_cost) ?? 0,
    shares: parseDecimalOrNull(dto.shares) ?? 0,
    averageEntry: parseDecimalOrNull(dto.average_entry_price),
    currentExitValue: parseDecimalOrNull(dto.current_exit_value),
    netPnl: parseDecimalOrNull(dto.net_pnl),
    freshness: formatFreshness(dto.freshness_as_of, now),
    detail: PAPER_DETAIL_LABELS[state],
    href: `/matches/${encodeURIComponent(dto.match_id)}`,
  }
}

export function toPulseRow(dto: PulseRowDto, now: Date): PulseRowModel {
  const [one, two] = namesOf(dto)
  const priority: PulseRowModel['priority'] =
    dto.kind === 'position'
      ? dto.action === 'sell'
        ? 'sell'
        : 'position'
      : dto.action === 'buy'
        ? dto.phase === 'live'
          ? 'buy_live'
          : 'buy_upcoming'
        : 'wait'
  return {
    id: `${dto.kind}:${dto.match_id}`,
    priority,
    match: `${one} vs. ${two}`,
    tournament: dto.tournament_name ?? '—',
    phase: dto.phase === 'live' ? '直播' : dto.phase === 'upcoming' ? '即将开始' : '已完赛',
    modelProbability: dto.model_probability,
    executableProbability: dto.executable_probability,
    edgePp:
      dto.conservative_net_edge === null
        ? null
        : parseDecimalOrNull(dto.conservative_net_edge) === null
          ? null
          : (parseDecimalOrNull(dto.conservative_net_edge) as number) * 100,
    state: dto.action as DecisionState,
    freshness: formatFreshness(dto.as_of, now, dto.is_stale || dto.has_gap),
    stale: dto.is_stale,
    overlay: overlayOf(dto.is_stale, dto.has_gap),
    href: `/matches/${encodeURIComponent(dto.match_id)}`,
  }
}

const PULSE_PRIORITY: Record<PulseRowModel['priority'], number> = {
  position: 0,
  sell: 0,
  buy_live: 1,
  buy_upcoming: 2,
  wait: 3,
}

/** Defensive client mirror of the server selection contract: one reserved
 * urgent-position row, then live BUY → upcoming BUY → strongest WAIT, capped
 * at three. Stable within groups; the server order is already canonical. */
export function selectHomePulseRows(rows: PulseRowModel[]): PulseRowModel[] {
  let reservedPosition: PulseRowModel | null = null
  const rest: PulseRowModel[] = []
  for (const row of rows) {
    if (
      reservedPosition === null &&
      (row.priority === 'position' || row.priority === 'sell')
    ) {
      reservedPosition = row
      continue
    }
    rest.push(row)
  }
  const ordered = [...rest].sort(
    (a, b) => PULSE_PRIORITY[a.priority] - PULSE_PRIORITY[b.priority],
  )
  const selected = reservedPosition ? [reservedPosition, ...ordered] : ordered
  return selected.slice(0, 3)
}

export function decisionToPulseOverlay(decision: DecisionSnapshotDto): DecisionOverlay {
  return overlayOf(decision.is_stale, decision.has_gap)
}
