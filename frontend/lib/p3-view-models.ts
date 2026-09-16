// Production P3 view models (T68): map canonical backend DTOs onto the
// frozen v0 row shapes. Presentation-only: every number/edge/action comes
// from the server; nothing here derives probability, edge, fills or
// settlement. Decimal strings are parsed for display formatting only, and
// absent values stay null so rows render an honest '—'.
import type {
  DecisionSnapshotDto,
  MarketSummaryDto,
  OpportunityDto,
  PaperPositionDto,
  PulseRowDto,
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
  covered: boolean
  state: DecisionState
  playerOne: string
  playerTwo: string
  playerOneAsk: number | null
  playerTwoAsk: number | null
  spread: number | null
  depth: number | null
  modelProbability: number | null
  reason: string
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
  state: 'entry_pending' | 'hold' | 'exit_pending' | 'exited' | 'missed' | 'settled'
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
  main: '主巡',
  atp: 'ATP',
  wta: 'WTA',
  challenger: 'Challenger',
  itf: 'ITF',
  other: '其他',
}

const REASON_LABELS: Record<string, string> = {
  MARKET_UNMAPPED: '未映射到比赛 · 仅市场数据',
  MODEL_UNPROMOTED: '模型未晋升 · 仅市场数据',
  PROMOTION_NOT_GRANTED: '晋升未授予 · 仅市场数据',
  ARTIFACT_INVALID: '模型工件无效 · 仅市场数据',
  POLICY_DISABLED: '策略未启用 · 仅市场数据',
  OUT_OF_DOMAIN: '覆盖范围外 · 仅市场数据',
  DATA_INCOMPLETE: '比分数据不完整 · 等待恢复',
  MODEL_DISAGREEMENT: '模型分歧 · 保持观望',
  RULE_CHANGED: '规则已变更 · 动作撤销',
  STALE: '报价过期 · 动作撤销',
  GAP: '数据缺口 · 动作撤销',
  INSUFFICIENT_LIQUIDITY: '深度不足以执行 $10',
  NO_NET_EDGE: '保守净 edge 未达门槛',
}

const PAPER_DETAIL_LABELS: Record<PaperRowModel['state'], string> = {
  entry_pending: 'FOK 意图已提交 · 等待延迟窗口',
  hold: '已成交 · 单次退出待触发',
  exit_pending: 'FOK 退出意图已提交',
  exited: '已按退出报价成交',
  missed: '入场未成交 · 不再重试',
  settled: '已按市场最终 resolution 结算',
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
  const prefix = stale ? '最后可信 · ' : ''
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
  const reason =
    dto.reason_code !== null
      ? (REASON_LABELS[dto.reason_code] ?? dto.reason_code)
      : dto.model_covered
        ? '模型覆盖 · 等待下一决策周期'
        : '仅市场数据'
  return {
    id: dto.market_id,
    match: dto.match_id ? `${one} vs. ${two}` : (dto.question ?? '—'),
    tournament: dto.tournament_name ?? '—',
    tier,
    tierLabel: TIER_LABELS[tier] ?? tier,
    gender: dto.gender ?? 'unknown',
    phase,
    covered: dto.model_covered,
    state: (dto.action ?? 'market_only') as DecisionState,
    playerOne: one,
    playerTwo: two,
    playerOneAsk: dto.outcome_asks ? parseDecimalOrNull(dto.outcome_asks[0]) : null,
    playerTwoAsk: dto.outcome_asks ? parseDecimalOrNull(dto.outcome_asks[1]) : null,
    spread: parseDecimalOrNull(dto.spread),
    depth: parseDecimalOrNull(dto.depth_usd),
    modelProbability: dto.model_probability,
    reason,
    freshness: formatFreshness(dto.as_of, now, dto.is_stale || dto.has_gap),
    stale: dto.is_stale,
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
  exit_missed: 'missed',
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
