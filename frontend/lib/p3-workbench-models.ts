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
  selectionLocalizedName: string | null
  modelProbability: number | null
  executableProbability: number | null
  edgePp: number | null
  quoteSide: 'ask' | 'bid' | 'market'
  maxBuyPrice: number | null
  confidenceLabel: string
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
  localizedName: string | null
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
  market_only: '仅显示市场报价',
  no_bet: '暂不参与',
  wait: '等待更好价格',
  buy: '模拟买入机会',
  entry_pending: '等待买入确认',
  missed: '未模拟买入',
  hold: '模拟持有中',
  sell: '模拟退出机会',
  exit_pending: '等待退出确认',
  exited: '已模拟退出',
  exit_missed: '退出未成交',
  settled: '已结算',
}

const GATE_LABELS: Record<string, string> = {
  mapping: '比赛信息匹配',
  rules: '市场规则',
  model: '判断依据',
  policy: '评估条件',
  liquidity: '可交易金额',
  net_edge: '模型与市场差距',
  overlay: '数据是否及时',
  position: '模拟持仓',
  pre_position: '买入条件',
}

const REASON_LABELS: Record<string, string> = {
  MARKET_UNMAPPED: '暂时无法确认该市场对应的比赛',
  MODEL_UNPROMOTED: '胜率估算仍在验证，目前仅显示市场报价',
  PROMOTION_NOT_GRANTED: '胜率估算仍在验证，目前仅显示市场报价',
  ARTIFACT_INVALID: '胜率估算暂不可用，目前仅显示市场报价',
  POLICY_DISABLED: '目前仅显示市场报价，暂不提供胜率估算',
  OUT_OF_DOMAIN: '该场比赛暂未提供胜率估算',
  DATA_INCOMPLETE: '比赛数据不完整，暂时无法评估',
  MODEL_DISAGREEMENT: '不同分析结果不一致，暂不提供建议',
  RULE_CHANGED: '市场规则有变化，已暂停新的模拟操作',
  STALE: '市场报价更新较慢，已暂停新的模拟操作',
  GAP: '比赛数据更新中断，已暂停新的模拟操作',
  INSUFFICIENT_LIQUIDITY: '当前可交易金额不足',
  NO_NET_EDGE: '模型估算与市场报价差距不明显',
}

const NO_FILL_LABELS: Record<string, string> = {
  DEPTH_INSUFFICIENT: '可交易金额不足',
  PRICE_EXCEEDED: '价格高于预期',
  EXPIRED: '报价已过期',
  BOOK_UNVERIFIABLE: '暂时无法确认可成交价格',
  POSITION_MISSING: '未找到对应的模拟持仓',
}

const AVAILABILITY_LABELS: Record<string, string> = {
  available: '可评估',
  degraded: '部分比赛数据缺失',
  unpromoted: '模型仍在验证',
  unavailable: '暂不可评估',
}

const EVENT_COPY: Record<
  string,
  { title: string; detail: string; status: 'complete' | 'pending' | 'missed' }
> = {
  entry_intent: {
    title: '已提交模拟买入',
    detail: '10 美元模拟订单，正在确认价格与可交易金额',
    status: 'pending',
  },
  entry_fill: {
    title: '模拟买入已成交',
    detail: '模拟持仓已建立',
    status: 'complete',
  },
  entry_no_fill: {
    title: '模拟买入未成交',
    detail: '价格或可交易金额不符合预期',
    status: 'missed',
  },
  exit_intent: {
    title: '已提交模拟退出',
    detail: '正在确认可成交价格',
    status: 'pending',
  },
  exit_fill: {
    title: '模拟退出已成交',
    detail: '模拟持仓已关闭，记录已保留',
    status: 'complete',
  },
  exit_no_fill: {
    title: '退出未成交',
    detail: '模拟持仓仍然开放',
    status: 'missed',
  },
  settled: {
    title: '比赛结果已结算',
    detail: '模拟结果已按最终赛果记录',
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

const workbenchClockFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
})

export function formatClock(iso: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return workbenchClockFormatter.format(date)
}

function pct(value: number | null): string {
  return value === null ? '—' : `${(value * 100).toFixed(1)}%`
}

function edgeText(value: number | null): string {
  return value === null ? '—' : `${value > 0 ? '+' : ''}${value.toFixed(1)} 个百分点`
}

const STATE_FALLBACK_REASON: Record<WorkbenchState, string> = {
  market_only: '目前只显示市场报价，暂无模型判断。',
  no_bet: '模型与市场价格差距不明显，暂不建议模拟买入。',
  wait: '这个方向值得关注，但当前价格偏高。',
  buy: '比赛数据与市场报价符合模拟买入条件。',
  entry_pending: '模拟买入已提交，正在确认是否成交。',
  missed: '当前价格已超出预期，本次模拟买入未成交。',
  hold: '模拟持仓仍在进行，暂未出现退出信号。',
  sell: '当前价格已达到模拟退出条件。',
  exit_pending: '模拟退出已提交，正在确认是否成交。',
  exited: '模拟持仓已退出，记录已保留。',
  exit_missed: '模拟退出未成交，持仓仍然开放。',
  settled: '比赛结果已确认，模拟记录已结算。',
}

export function toDecisionSummaryModel(
  snapshot: DecisionSnapshotDto,
  selectionName: string | null,
  now: Date,
  selectionLocalizedName: string | null = null,
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
      title = `${selectionName ?? '所选球员'} 出现模拟买入机会`
      description = `模型估算胜率 ${pct(modelProbability)}，10 美元模拟买入均价 ${pct(executableProbability)}，估算优势 ${edgeText(edgePp)}。`
      break
    case 'wait':
      title = '可以关注，但当前价格偏高'
      description =
        maxBuyPrice !== null
          ? `价格回落到 ${pct(maxBuyPrice)} 或以下时，可以重新评估。`
          : '等价格更合适时，再重新评估这个方向。'
      break
    case 'hold':
      title = '模拟持仓中'
      description = `模型估算胜率 ${pct(modelProbability)}；当前模拟卖出价格 ${pct(executableProbability)}。`
      break
    case 'sell':
      title = '出现模拟退出机会'
      description = `当前模拟卖出价格 ${pct(executableProbability)}；模型估算胜率 ${pct(modelProbability)}。`
      break
    case 'settled':
      title = '模拟记录已结算'
      description = '比赛结果已核验，模拟结果已记录。'
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
        ? (REASON_LABELS[snapshot.reason_code] ?? '系统暂未提供更多判断原因')
        : STATE_FALLBACK_REASON[state],
    selectionLabel: selectionName ?? '—',
    selectionLocalizedName,
    modelProbability,
    executableProbability,
    edgePp,
    quoteSide:
      snapshot.quote_side === 'entry' ? 'ask' : snapshot.quote_side === 'exit' ? 'bid' : 'market',
    maxBuyPrice,
    confidenceLabel: availability
      ? (AVAILABILITY_LABELS[availability] ?? '暂不可评估')
      : '—',
    modelAvailability: availability,
    modelVersion: snapshot.model_version ?? '—',
    dataVersion: snapshot.data_version ?? '—',
    marketFreshness: `报价更新 · ${age}`,
    modelFreshness: `模型更新 · ${clock}`,
    asOf: clock,
    overlay: workbenchOverlay(snapshot),
    actionAvailable: state === 'buy' || state === 'sell',
  }
}

const STATE_EYEBROW: Record<WorkbenchState, string> = {
  market_only: '仅显示市场报价',
  no_bet: '当前不建议模拟买入',
  wait: '等待更合适的价格',
  buy: '模拟买入机会',
  entry_pending: '等待成交确认',
  missed: '模拟买入未成交',
  hold: '模拟持仓进行中',
  sell: '模拟退出机会',
  exit_pending: '等待退出确认',
  exited: '模拟持仓已退出',
  exit_missed: '模拟退出未成交',
  settled: '模拟记录已结算',
}

function defaultTitle(state: WorkbenchState, selectionName: string | null): string {
  switch (state) {
    case 'market_only':
      return '目前只显示市场报价'
    case 'no_bet':
      return '模型与市场价格差距不明显'
    case 'entry_pending':
      return '等待买入确认，尚未成交'
    case 'missed':
      return '价格已超出预期，本次模拟买入未成交'
    case 'exit_pending':
      return '等待退出确认，模拟持仓仍然开放'
    case 'exited':
      return `${selectionName ?? '所选球员'} 的模拟持仓已退出`
    case 'exit_missed':
      return '退出未成交，模拟持仓仍然开放'
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
      return '这里只显示市场买入和卖出报价；这类比赛暂不提供模型估算。'
    case 'no_bet':
      return `模型估算胜率 ${pct(modelProbability)}，10 美元模拟买入均价 ${pct(executableProbability)}；扣除成本后的价格差距不明显。`
    case 'entry_pending':
      return '10 美元模拟订单正在确认价格与可交易金额。'
    case 'missed':
      return '价格已超出预期，本次模拟买入没有成交。'
    case 'exit_pending':
      return '模拟退出正在确认是否成交；确认前仍显示为持仓中。'
    case 'exited':
      return '模拟退出已确认，记录已保留。'
    case 'exit_missed':
      return '模拟退出没有成交，持仓仍然开放。'
    default:
      return ''
  }
}

function relativeAge(iso: string | null, now: Date): string {
  if (!iso) return '更新时间暂不可用'
  const then = new Date(iso).getTime()
  if (!Number.isFinite(then)) return '更新时间暂不可用'
  const seconds = Math.max(0, Math.floor((now.getTime() - then) / 1000))
  if (seconds < 5) return '刚刚'
  if (seconds < 60) return `${seconds} 秒前`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} 分前`
  return `${Math.floor(minutes / 60)} 小时前`
}

export function toEvidenceModel(snapshot: DecisionSnapshotDto): EvidenceModel {
  const gates: EvidenceGateModel[] = snapshot.gates.map((gate) => ({
    label: GATE_LABELS[gate.gate] ?? '其他条件',
    detail: gate.passed
      ? '已满足'
      : (gate.reason_code ? (REASON_LABELS[gate.reason_code] ?? '暂未满足') : '暂未满足'),
    status: gate.passed ? 'pass' : 'fail',
  }))
  const reasons: string[] = []
  if (snapshot.reason_code !== null) {
    reasons.push(REASON_LABELS[snapshot.reason_code] ?? '系统暂未提供更多判断原因')
  }
  for (const gate of snapshot.gates) {
    if (!gate.passed) {
      reasons.push(
        `暂未满足：${GATE_LABELS[gate.gate] ?? '其他条件'}${
          gate.reason_code ? `（${REASON_LABELS[gate.reason_code] ?? '条件未满足'}）` : ''
        }`,
      )
    }
  }
  if (snapshot.is_stale) reasons.push('市场报价更新较慢，已暂停新的模拟操作')
  if (snapshot.has_gap) reasons.push('比赛数据更新中断，已暂停新的模拟操作')
  if (snapshot.lock_profit_available) reasons.push('当前价格已达到预设的模拟退出条件')
  if (reasons.length === 0) reasons.push('比赛与市场数据均符合当前评估条件。')
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
        ? '模型暂不可评估，目前只显示市场报价。'
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
              '系统暂未提供更多说明'
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
  playerLocalizedNameById: Record<string, string | null> = {},
): ChartSideModel[] {
  return snapshot.outcome_levels.map((level) => ({
    playerId: level.player_id,
    name: playerNameById[level.player_id] ?? level.player_id,
    localizedName: playerLocalizedNameById[level.player_id] ?? null,
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
