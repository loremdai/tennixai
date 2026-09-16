// T69 workbench view models. Everything rendered comes from the server
// decision snapshot (single source of the current action): state derivation
// only sequences server-provided lifecycle/position/action facts, numbers
// are parsed decimal strings for display formatting, and copy tables are
// presentation labels. No probability, edge, fill, settlement or lifecycle
// is ever calculated here.
import type { DecisionSnapshotDto } from '@/lib/api/types'
import type { DecisionOverlay, DecisionState } from '@/components/p3/p3-preview-data'
import { parseDecimalOrNull } from '@/lib/p3-view-models'

export type WorkbenchState = DecisionState

export type DecisionSummaryModel = {
  state: WorkbenchState
  stateLabel: string
  eyebrow: string
  title: string
  description: string
  reason: string
  selectionLabel: string
  modelProbability: number | null
  executableProbability: number | null
  edgePp: number | null
  quoteSide: 'ask' | 'bid' | 'market'
  maxBuyPrice: number | null
  paperEv: number | null
  confidenceLabel: string
  confidenceValue: number | null
  modelAvailability: string | null
  modelVersion: string
  dataVersion: string
  marketFreshness: string
  modelFreshness: string
  asOf: string
  overlay: DecisionOverlay
  actionAvailable: boolean
}

export type EvidenceGateModel = {
  label: string
  detail: string
  status: 'pass' | 'fail' | 'unknown'
}

export type EvidenceModel = {
  gates: EvidenceGateModel[]
  reasons: string[]
  modelVersion: string
  calibrationVersion: string
  policyVersion: string
  dataVersion: string
  asOf: string
  availabilityBanner: string | null
}

export type PaperEventModel = {
  id: string
  time: string
  title: string
  detail: string
  status: 'complete' | 'pending' | 'missed' | 'neutral'
}

export type PaperModel = {
  state: WorkbenchState
  entryCost: number
  averageEntry: number | null
  shares: number
  currentExitValue: number | null
  netPnl: number | null
  events: PaperEventModel[]
}

export type ChartSideModel = {
  playerId: string
  name: string
  modelProbability: number | null
  ask: number | null
  bid: number | null
  selected: boolean
}

export type TrajectoryPointModel = {
  time: string
  model: number | null
  market: number | null
  uncertainty: [number, number] | null
}

export const STATE_LABELS: Record<WorkbenchState, string> = {
  market_only: 'MARKET ONLY',
  no_bet: 'NO BET',
  wait: 'WAIT',
  buy: 'BUY',
  entry_pending: 'ENTRY PENDING',
  missed: 'MISSED',
  hold: 'FILLED / HOLD',
  sell: 'SELL',
  exit_pending: 'EXIT PENDING',
  exited: 'EXITED',
  exit_missed: 'EXIT MISSED',
  settled: 'SETTLED',
}

const GATE_LABELS: Record<string, string> = {
  mapping: '市场映射',
  rules: '规则一致性',
  model: '模型可用性',
  policy: '策略门槛',
  liquidity: '深度与最小单',
  net_edge: '保守净 edge',
  overlay: '新鲜度叠加',
  position: '仓位状态',
  pre_position: '入场前置',
}

const REASON_LABELS: Record<string, string> = {
  MARKET_UNMAPPED: '市场未映射到比赛，仅展示市场数据',
  MODEL_UNPROMOTED: '模型未晋升：不生成 BUY/SELL，只展示市场数据',
  PROMOTION_NOT_GRANTED: '晋升未授予：保持 NO BET',
  ARTIFACT_INVALID: '模型工件校验失败：fail-closed',
  POLICY_DISABLED: '策略未启用：保持 NO BET',
  OUT_OF_DOMAIN: '赛事在模型覆盖范围外，仅展示市场数据',
  DATA_INCOMPLETE: '比分数据不完整，等待恢复后重估',
  MODEL_DISAGREEMENT: '模型分歧超过门槛，保持观望',
  RULE_CHANGED: '市场规则已变更，动作已撤销',
  STALE: '报价超过 freshness 阈值，动作已撤销',
  GAP: '数据缺口，动作已撤销且不插值',
  INSUFFICIENT_LIQUIDITY: '深度不足以执行 $10',
  NO_NET_EDGE: '保守净 edge 未达门槛',
}

const NO_FILL_LABELS: Record<string, string> = {
  DEPTH_INSUFFICIENT: '深度不足以执行 $10',
  PRICE_EXCEEDED: '价格超出上限',
  EXPIRED: '意图已过期',
  BOOK_UNVERIFIABLE: '订单簿不可核验',
  POSITION_MISSING: '仓位缺失',
}

const AVAILABILITY_LABELS: Record<string, string> = {
  available: '模型可用',
  degraded: '降级 · 仅比分缺失',
  unpromoted: '模型未晋升',
  unavailable: '模型不可用',
}

const EVENT_COPY: Record<
  string,
  { title: string; detail: string; status: 'complete' | 'pending' | 'missed' }
> = {
  entry_intent: {
    title: 'Paper entry intent 已记录',
    detail: '$10 FOK · 等待延迟窗口与深度核验',
    status: 'pending',
  },
  entry_fill: {
    title: '入场 FOK 全部成交',
    detail: '主 Paper position 已开放；一次性，不追加',
    status: 'complete',
  },
  entry_no_fill: {
    title: '入场未成交',
    detail: 'typed no-fill；不重试、不追价、不回写成交',
    status: 'missed',
  },
  exit_intent: {
    title: 'Paper exit intent 已记录',
    detail: '$10 FOK 退出 · 等待确认',
    status: 'pending',
  },
  exit_fill: {
    title: '退出 FOK 全部成交',
    detail: '仓位已关闭；记录永久保留',
    status: 'complete',
  },
  exit_no_fill: {
    title: '退出未成交',
    detail: '仓位保持开放并继续持有至结算',
    status: 'missed',
  },
  settled: {
    title: '已按市场最终 resolution 结算',
    detail: 'EV exit、HODL 与 convergence-lock 三轨均保留',
    status: 'complete',
  },
}

/** The single current-action source: server lifecycle/position/action
 * facts sequenced into exactly one of the twelve canonical states. */
export function deriveWorkbenchState(snapshot: DecisionSnapshotDto): WorkbenchState {
  const lifecycle = snapshot.lifecycle
  const status = snapshot.position?.status ?? null
  if (status === 'settled' || lifecycle.includes('settled')) return 'settled'
  if (status === 'exit_missed' || lifecycle.includes('exit_missed')) return 'exit_missed'
  if (status === 'exited' || lifecycle.includes('exited')) return 'exited'
  if (status === 'exit_pending' || lifecycle.includes('exit_pending')) return 'exit_pending'
  if (status === 'missed' || lifecycle.includes('missed')) return 'missed'
  if (
    status === 'entry_pending' ||
    (lifecycle.includes('entry_pending') && !lifecycle.includes('filled'))
  ) {
    return 'entry_pending'
  }
  if (status === 'open') return snapshot.action === 'sell' ? 'sell' : 'hold'
  switch (snapshot.action) {
    case 'buy':
      return 'buy'
    case 'wait':
      return 'wait'
    case 'sell':
      return 'sell'
    case 'hold':
      return 'hold'
    case 'no_bet':
      return 'no_bet'
    case 'market_only':
    default:
      return 'market_only'
  }
}

export function workbenchOverlay(snapshot: DecisionSnapshotDto): DecisionOverlay {
  if (snapshot.is_stale) return 'stale'
  if (snapshot.has_gap) return 'gap'
  return 'none'
}

export function formatClock(iso: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleTimeString('zh-MO', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

function pct(value: number | null): string {
  return value === null ? '—' : `${(value * 100).toFixed(1)}%`
}

function edgeText(value: number | null): string {
  return value === null ? '—' : `${value > 0 ? '+' : ''}${value.toFixed(1)}pp`
}

const STATE_FALLBACK_REASON: Record<WorkbenchState, string> = {
  market_only: '仅展示两侧独立可执行报价；不伪造模型概率或 edge。',
  no_bet: '模型可用，但保守净 edge 未达决策门槛。',
  wait: '方向成立；等待可执行均价回到最高可买价或更低。',
  buy: '覆盖、新鲜度、深度与净 edge 全部 hard gate 通过。',
  entry_pending: '供应商尚未返回可核验成交结果；pending 不等于 filled。',
  missed: '入场 intent 已关闭，没有仓位，也不会回写为成交。',
  hold: '仓位开放；尚未达到止盈或模型反转门槛。',
  sell: '退出报价触发退出 gate；记录 SELL 研究信号。',
  exit_pending: '退出 intent 等待确认；确认前不记为已退出。',
  exited: '退出成交已核验，生命周期记录永久保留。',
  exit_missed: '退出未成交；仓位保持开放并持有至结算。',
  settled: '结算只服从市场最终 resolution；三轨结果均保留。',
}

export function toDecisionSummaryModel(
  snapshot: DecisionSnapshotDto,
  selectionName: string | null,
  now: Date,
): DecisionSummaryModel {
  const state = deriveWorkbenchState(snapshot)
  const modelProbability =
    snapshot.model_probabilities && snapshot.target_player_id
      ? (snapshot.model_probabilities[snapshot.target_player_id] ?? null)
      : null
  const executableProbability = parseDecimalOrNull(snapshot.quote_average_price)
  const edgePpRaw = parseDecimalOrNull(snapshot.conservative_net_edge)
  const edgePp = edgePpRaw === null ? null : edgePpRaw * 100
  const maxBuyPrice = parseDecimalOrNull(snapshot.max_acceptable_price)
  const availability = snapshot.model_availability
  const clock = formatClock(snapshot.as_of)
  const age = relativeAge(snapshot.as_of, now)
  let title: string
  let description: string
  switch (state) {
    case 'buy':
      title = `${selectionName ?? '目标方向'} 进入策略价格窗口`
      description = `模型概率 ${pct(modelProbability)}，$10 可执行市场概率 ${pct(executableProbability)}，保守 edge ${edgeText(edgePp)}。`
      break
    case 'wait':
      title = '观点有效，但当前报价超过最高可买价'
      description =
        maxBuyPrice !== null
          ? `等待可执行均价回到 ${pct(maxBuyPrice)} 或更低，再重新评估 Paper intent。`
          : '等待可执行均价回到策略门槛，再重新评估 Paper intent。'
      break
    case 'hold':
      title = '仓位已成交，当前建议继续持有'
      description = `模型概率 ${pct(modelProbability)}；退出价值 ${pct(executableProbability)}。`
      break
    case 'sell':
      title = '退出报价触发退出 gate，记录 SELL 信号'
      description = `当前可执行 bid ${pct(executableProbability)}；最新模型 ${pct(modelProbability)}。`
      break
    case 'settled':
      title = 'Paper market 已按最终 resolution 结算'
      description = '结算结果已核验；EV exit、HODL 与 convergence-lock 轨迹均保留。'
      break
    default:
      title = STATE_FALLBACK_REASON[state]
      description = ''
  }
  if (state === 'market_only' || state === 'no_bet' || state === 'missed' || state === 'entry_pending' || state === 'exit_pending' || state === 'exited' || state === 'exit_missed') {
    title = defaultTitle(state, selectionName)
    description = defaultDescription(state, modelProbability, executableProbability)
  }
  return {
    state,
    stateLabel: STATE_LABELS[state],
    eyebrow: STATE_EYEBROW[state],
    title,
    description,
    reason:
      snapshot.reason_code !== null
        ? (REASON_LABELS[snapshot.reason_code] ?? snapshot.reason_code)
        : STATE_FALLBACK_REASON[state],
    selectionLabel: selectionName ?? '—',
    modelProbability,
    executableProbability,
    edgePp,
    quoteSide:
      snapshot.quote_side === 'entry' ? 'ask' : snapshot.quote_side === 'exit' ? 'bid' : 'market',
    maxBuyPrice,
    paperEv: parseDecimalOrNull(snapshot.hold_value),
    confidenceLabel: availability ? (AVAILABILITY_LABELS[availability] ?? availability) : '—',
    confidenceValue: null,
    modelAvailability: availability,
    modelVersion: snapshot.model_version ?? '—',
    dataVersion: snapshot.data_version ?? '—',
    marketFreshness: `报价 · ${age}`,
    modelFreshness: `模型 · ${clock}`,
    asOf: clock,
    overlay: workbenchOverlay(snapshot),
    actionAvailable: state === 'buy' || state === 'sell',
  }
}

const STATE_EYEBROW: Record<WorkbenchState, string> = {
  market_only: '仅市场可见',
  no_bet: '已覆盖 · 不行动',
  wait: '方向成立 · 等待价格',
  buy: '研究机会 · Paper only',
  entry_pending: 'Paper intent 已记录',
  missed: 'Paper intent 未成交',
  hold: '开放 Paper position',
  sell: '开放 Paper position',
  exit_pending: 'Paper exit intent 已记录',
  exited: 'Paper position 已关闭',
  exit_missed: 'Paper exit 未成交',
  settled: 'Paper market 已结算',
}

function defaultTitle(state: WorkbenchState, selectionName: string | null): string {
  switch (state) {
    case 'market_only':
      return '该市场暂不生成模型判断'
    case 'no_bet':
      return '价格接近模型判断，没有足够优势'
    case 'entry_pending':
      return '等待入场报价确认，尚未成交'
    case 'missed':
      return '报价跳离上限，本次机会已错过'
    case 'exit_pending':
      return '等待退出报价确认，仓位仍然开放'
    case 'exited':
      return `${selectionName ?? '目标'} 方向仓位已退出`
    case 'exit_missed':
      return '退出报价撤回，仓位仍然开放'
    default:
      return STATE_FALLBACK_REASON[state]
  }
}

function defaultDescription(
  state: WorkbenchState,
  modelProbability: number | null,
  executableProbability: number | null,
): string {
  switch (state) {
    case 'market_only':
      return '仅展示两侧独立可执行报价；此市场不在模型覆盖范围内。'
    case 'no_bet':
      return `模型概率 ${pct(modelProbability)}，$10 可执行市场概率 ${pct(executableProbability)}；净 edge 未达门槛。`
    case 'entry_pending':
      return `$10 Paper intent 正等待可执行报价确认；pending 不等于 filled。`
    case 'missed':
      return '入场 intent 已关闭，没有仓位，也不会回写为成交。'
    case 'exit_pending':
      return '退出 intent 正等待可执行报价确认；在确认前不记为已退出。'
    case 'exited':
      return '退出成交已核验，生命周期记录永久保留。'
    case 'exit_missed':
      return '退出 intent 已标记 missed；不能把未成交状态显示为已退出。'
    default:
      return ''
  }
}

function relativeAge(iso: string | null, now: Date): string {
  if (!iso) return '时间未知'
  const then = new Date(iso).getTime()
  if (!Number.isFinite(then)) return '时间未知'
  const seconds = Math.max(0, Math.floor((now.getTime() - then) / 1000))
  if (seconds < 5) return '刚刚'
  if (seconds < 60) return `${seconds} 秒前`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} 分前`
  return `${Math.floor(minutes / 60)} 小时前`
}

export function toEvidenceModel(snapshot: DecisionSnapshotDto): EvidenceModel {
  const gates: EvidenceGateModel[] = snapshot.gates.map((gate) => ({
    label: GATE_LABELS[gate.gate] ?? gate.gate,
    detail: gate.passed
      ? '通过'
      : (gate.reason_code
          ? (REASON_LABELS[gate.reason_code] ?? gate.reason_code)
          : '未通过'),
    status: gate.passed ? 'pass' : 'fail',
  }))
  const reasons: string[] = []
  if (snapshot.reason_code !== null) {
    reasons.push(REASON_LABELS[snapshot.reason_code] ?? snapshot.reason_code)
  }
  for (const gate of snapshot.gates) {
    if (!gate.passed) {
      reasons.push(
        `hard gate 未通过 · ${GATE_LABELS[gate.gate] ?? gate.gate}${
          gate.reason_code ? `（${REASON_LABELS[gate.reason_code] ?? gate.reason_code}）` : ''
        }`,
      )
    }
  }
  if (snapshot.is_stale) reasons.push('报价超过 freshness 阈值 · 新动作已撤销')
  if (snapshot.has_gap) reasons.push('数据缺口 · 新动作已撤销且不插值')
  if (snapshot.lock_profit_available) reasons.push('止盈退出可用（仅诊断信息）')
  if (reasons.length === 0) reasons.push('全部 hard gate 通过；证据与版本如下。')
  const availability = snapshot.model_availability
  return {
    gates,
    reasons,
    modelVersion: snapshot.model_version ?? '—',
    calibrationVersion: snapshot.calibration_version ?? '—',
    policyVersion: snapshot.policy_version ?? '—',
    dataVersion: snapshot.data_version ?? '—',
    asOf: formatClock(snapshot.as_of),
    availabilityBanner:
      availability === 'unpromoted' || availability === 'unavailable'
        ? '模型未晋升或不可用：本页只展示市场数据与 NO BET，不会生成 BUY/SELL。'
        : null,
  }
}

export function toPaperModel(snapshot: DecisionSnapshotDto): PaperModel | null {
  const position = snapshot.position
  if (!position) return null
  const events: PaperEventModel[] = position.events.map((event, index) => {
    const copy = EVENT_COPY[event.kind] ?? {
      title: event.kind,
      detail: '',
      status: 'neutral' as const
    }
    const isLast = index === position.events.length - 1
    return {
      id: event.id,
      time: formatClock(event.at),
      title: copy.title,
      detail:
        event.reason_code !== null
          ? `${copy.detail} · ${
              NO_FILL_LABELS[event.reason_code] ??
              REASON_LABELS[event.reason_code] ??
              event.reason_code
            }`
          : copy.detail,
      status: copy.status === 'pending' && !isLast ? 'complete' : copy.status,
    }
  })
  return {
    state: deriveWorkbenchState(snapshot),
    entryCost: parseDecimalOrNull(position.entry_cost) ?? 0,
    averageEntry: parseDecimalOrNull(position.average_entry_price),
    shares: parseDecimalOrNull(position.shares) ?? 0,
    currentExitValue: parseDecimalOrNull(position.current_exit_value),
    netPnl: parseDecimalOrNull(position.net_pnl),
    events,
  }
}

export function toChartSides(
  snapshot: DecisionSnapshotDto,
  playerNameById: Record<string, string>,
): ChartSideModel[] {
  return snapshot.outcome_levels.map((level) => ({
    playerId: level.player_id,
    name: playerNameById[level.player_id] ?? level.player_id,
    modelProbability: snapshot.model_probabilities
      ? (snapshot.model_probabilities[level.player_id] ?? null)
      : null,
    ask: parseDecimalOrNull(level.best_ask),
    bid: parseDecimalOrNull(level.best_bid),
    selected: level.player_id === snapshot.target_player_id,
  }))
}

const TRAJECTORY_LIMIT = 60

/** Session-local trajectory accumulator: each applied snapshot appends one
 * point; missing values stay null so the chart renders gaps, never
 * interpolated lines. No history is fabricated across reloads. */
export function appendTrajectoryPoint(
  points: TrajectoryPointModel[],
  snapshot: DecisionSnapshotDto,
): TrajectoryPointModel[] {
  const time = formatClock(snapshot.as_of)
  const last = points[points.length - 1]
  const model =
    snapshot.model_probabilities && snapshot.target_player_id
      ? (snapshot.model_probabilities[snapshot.target_player_id] ?? null)
      : null
  const market = parseDecimalOrNull(snapshot.quote_average_price)
  if (last && last.time === time && last.model === model && last.market === market) {
    return points
  }
  return [...points, { time, model, market, uncertainty: null }].slice(-TRAJECTORY_LIMIT)
}
