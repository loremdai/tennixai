export const DECISION_STATES = [
  'market_only',
  'no_bet',
  'wait',
  'buy',
  'entry_pending',
  'missed',
  'hold',
  'sell',
  'exit_pending',
  'exited',
  'exit_missed',
  'settled',
] as const

export type DecisionState = (typeof DECISION_STATES)[number]
export type DecisionOverlay = 'none' | 'stale' | 'gap'
export type ConfidenceState = 'high' | 'medium' | 'low' | 'empty' | 'error'
export type AnalysisState = 'expanded' | 'collapsed'
export type SelectionState = 'sinner' | 'alcaraz'
export type MethodologyState = 'closed' | 'open'
export type DecisionTone = 'positive' | 'pending' | 'neutral' | 'negative'

export type TrajectoryPoint = {
  time: string
  model: number | null
  market: number | null
  uncertainty: [number, number] | null
}

export type DecisionGate = {
  label: string
  detail: string
  status: 'pass' | 'fail' | 'unknown'
}

export type PaperEvent = {
  id: string
  time: string
  title: string
  detail: string
  status: 'complete' | 'pending' | 'missed' | 'neutral'
}

export type DecisionPreview = {
  state: DecisionState
  stateLabel: string
  tone: DecisionTone
  eyebrow: string
  title: string
  description: string
  reason: string
  selection: SelectionState
  selectionLabel: string
  modelProbability: number | null
  executableProbability: number
  edgePp: number | null
  quoteSide: 'ask' | 'bid' | 'market'
  maxBuyPrice: number | null
  paperEv: number | null
  confidence: ConfidenceState
  confidenceLabel: string
  confidenceValue: number | null
  modelVersion: string
  dataVersion: string
  marketFreshness: string
  modelFreshness: string
  asOf: string
  overlay: DecisionOverlay
  actionAvailable: boolean
  trajectory: TrajectoryPoint[]
  gates: DecisionGate[]
  reasons: string[]
  paper: {
    entryCost: number
    averageEntry: number
    shares: number
    currentExitValue: number
    netPnl: number
    events: PaperEvent[]
  } | null
}

export type HomePulseState = 'populated' | 'stale' | 'empty'
export type HomePulseRow = {
  id: string
  priority: 'position' | 'sell' | 'buy_live' | 'buy_upcoming' | 'wait'
  match: string
  tournament: string
  phase: '直播' | '即将开始' | '已完赛'
  modelProbability: number
  executableProbability: number
  edgePp: number
  state: DecisionState
  freshness: string
  stale: boolean
  href: string
}

export type MarketView = 'opportunities' | 'all' | 'paper'
export type MarketsPreviewState =
  | 'populated'
  | 'empty'
  | 'partial_stale'
  | 'filtered_empty'
  | 'supplier_empty'
  | 'open'
  | 'terminal'
  | 'resolution_pending'
  | 'error'
export type TourTier = 'main' | 'challenger' | 'itf' | 'other'
export type MarketGender = 'men' | 'women'
export type MatchPhase = 'live' | 'upcoming'

export type OpportunityPreview = {
  id: string
  match: string
  tournament: string
  phase: MatchPhase
  selection: string
  modelProbability: number
  executableProbability: number
  edgePp: number
  state: 'buy' | 'wait'
  maxBuyPrice: number | null
  freshness: string
  stale: boolean
  href: string
}

export type MarketListingPreview = {
  id: string
  match: string
  tournament: string
  tier: TourTier
  gender: MarketGender
  phase: MatchPhase
  covered: boolean
  state: 'no_bet' | 'market_only'
  playerOne: string
  playerTwo: string
  playerOneAsk: number
  playerTwoAsk: number
  spread: number
  depth: number
  modelProbability: number | null
  reason: string
  freshness: string
  stale: boolean
  href: string
}

export type PaperLedgerPreview = {
  id: string
  match: string
  tournament: string
  direction: string
  state: 'entry_pending' | 'hold' | 'exit_pending' | 'exited' | 'missed' | 'settled'
  cost: number
  shares: number
  averageEntry: number
  currentExitValue: number | null
  netPnl: number | null
  freshness: string
  detail: string
  href: string
}

const stateLabels: Record<DecisionState, string> = {
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

const stateTones: Record<DecisionState, DecisionTone> = {
  market_only: 'neutral',
  no_bet: 'neutral',
  wait: 'pending',
  buy: 'positive',
  entry_pending: 'pending',
  missed: 'negative',
  hold: 'positive',
  sell: 'negative',
  exit_pending: 'pending',
  exited: 'neutral',
  exit_missed: 'negative',
  settled: 'neutral',
}

const stateCopy: Record<DecisionState, Pick<DecisionPreview, 'eyebrow' | 'title' | 'description' | 'reason'>> = {
  market_only: {
    eyebrow: '仅市场可见',
    title: '该市场暂不生成模型判断',
    description: '仅展示两侧独立可执行报价；此赛事未进入主巡模型覆盖范围。',
    reason: '赛事级别未通过模型覆盖门槛，不能伪造概率或 edge。',
  },
  no_bet: {
    eyebrow: '已覆盖 · 不行动',
    title: '价格接近模型判断，没有足够优势',
    description: '模型可用，但保守净 edge 低于 3.0pp 决策门槛。',
    reason: '扣除 spread 与执行缓冲后，净 edge 仅 +1.6pp。',
  },
  wait: {
    eyebrow: '方向成立 · 等待价格',
    title: '观点有效，但当前报价超过最高可买价',
    description: '等待可执行均价回到 55.0% 或更低，再重新评估 Paper intent。',
    reason: '当前 $10 可执行均价高于策略价格门槛。',
  },
  buy: {
    eyebrow: '研究机会 · Paper only',
    title: 'Sinner 方向进入策略价格窗口',
    description: '模型概率 64.0%，$10 可执行市场概率 50.4%，保守 edge +13.6pp。',
    reason: '覆盖、数据新鲜度、深度和净 edge 四项 hard gate 均通过。',
  },
  entry_pending: {
    eyebrow: 'Paper intent 已记录',
    title: '等待入场报价确认，尚未成交',
    description: '$10 Paper intent 正等待 50.4% 或更优报价；pending 不等于 filled。',
    reason: '供应商尚未返回可核验成交结果。',
  },
  missed: {
    eyebrow: 'Paper intent 未成交',
    title: '报价跳离上限，本次机会已错过',
    description: '入场 intent 已关闭，没有仓位，也不会回写为成交。',
    reason: '可执行均价在确认前升至 56.6%，超过 55.0% 上限。',
  },
  hold: {
    eyebrow: '开放 Paper position',
    title: '仓位已成交，当前建议继续持有',
    description: '平均入场 50.4%，当前可退出价 61.8%；模型判断仍高于退出报价。',
    reason: '最新模型 64.0%，尚未达到止盈或模型反转门槛。',
  },
  sell: {
    eyebrow: '开放 Paper position',
    title: '退出报价超过保守价值，记录 SELL 信号',
    description: '当前可执行 bid 为 64.2%，高于最新模型 57.0%。',
    reason: '模型下修与市场上行同时触发退出 gate。',
  },
  exit_pending: {
    eyebrow: 'Paper exit intent 已记录',
    title: '等待退出报价确认，仓位仍然开放',
    description: '退出 intent 正等待 63.0% 或更优报价；在确认前不记为已退出。',
    reason: '供应商尚未返回可核验退出成交。',
  },
  exited: {
    eyebrow: 'Paper position 已关闭',
    title: '仓位按 63.0% 退出',
    description: '退出价值 $12.50，扣除执行缓冲后的净 P&L 为 +$2.50。',
    reason: '退出成交已核验，生命周期记录永久保留。',
  },
  exit_missed: {
    eyebrow: 'Paper exit 未成交',
    title: '退出报价撤回，仓位仍然开放',
    description: '退出 intent 已标记 missed；不能把未成交状态显示为已退出。',
    reason: 'bid 在确认前跌至 59.1%，低于 63.0% 最低退出价。',
  },
  settled: {
    eyebrow: 'Paper market 已结算',
    title: 'Sinner 方向按胜出结果结算',
    description: '每份按 $1.00 结算，最终净 P&L +$9.84。',
    reason: '结算结果已核验；EV exit、HODL 与 convergence-lock 轨迹均保留。',
  },
}

const confidenceValues: Record<ConfidenceState, { label: string; value: number | null; spread: number }> = {
  high: { label: '高置信度', value: 82, spread: 0.035 },
  medium: { label: '中置信度', value: 68, spread: 0.055 },
  low: { label: '低置信度', value: 43, spread: 0.09 },
  empty: { label: '置信度样本不足', value: null, spread: 0.12 },
  error: { label: '置信度计算失败', value: null, spread: 0.12 },
}

const baseTrajectory = [
  { time: '09:18', model: 0.58, market: 0.51 },
  { time: '09:24', model: 0.59, market: 0.522 },
  { time: '09:30', model: 0.61, market: 0.516 },
  { time: '09:36', model: 0.62, market: 0.511 },
  { time: '09:42', model: 0.635, market: 0.508 },
  { time: '09:48', model: 0.64, market: 0.504 },
]

const numberProfile: Record<DecisionState, {
  model: number | null
  market: number
  edge: number | null
  quoteSide: DecisionPreview['quoteSide']
  maxBuyPrice: number | null
  paperEv: number | null
}> = {
  market_only: { model: null, market: 0.504, edge: null, quoteSide: 'market', maxBuyPrice: null, paperEv: null },
  no_bet: { model: 0.52, market: 0.504, edge: 1.6, quoteSide: 'ask', maxBuyPrice: null, paperEv: 0.16 },
  wait: { model: 0.64, market: 0.572, edge: 6.8, quoteSide: 'ask', maxBuyPrice: 0.55, paperEv: 0.68 },
  buy: { model: 0.64, market: 0.504, edge: 13.6, quoteSide: 'ask', maxBuyPrice: 0.55, paperEv: 1.36 },
  entry_pending: { model: 0.64, market: 0.504, edge: 13.6, quoteSide: 'ask', maxBuyPrice: 0.55, paperEv: 1.36 },
  missed: { model: 0.64, market: 0.566, edge: 7.4, quoteSide: 'ask', maxBuyPrice: 0.55, paperEv: null },
  hold: { model: 0.64, market: 0.618, edge: 2.2, quoteSide: 'bid', maxBuyPrice: null, paperEv: 1.36 },
  sell: { model: 0.57, market: 0.642, edge: -7.2, quoteSide: 'bid', maxBuyPrice: null, paperEv: null },
  exit_pending: { model: 0.57, market: 0.63, edge: -6, quoteSide: 'bid', maxBuyPrice: null, paperEv: null },
  exited: { model: 0.57, market: 0.63, edge: -6, quoteSide: 'bid', maxBuyPrice: null, paperEv: null },
  exit_missed: { model: 0.57, market: 0.591, edge: -2.1, quoteSide: 'bid', maxBuyPrice: null, paperEv: null },
  settled: { model: 0.91, market: 1, edge: null, quoteSide: 'market', maxBuyPrice: null, paperEv: null },
}

function event(id: string, time: string, title: string, detail: string, status: PaperEvent['status']): PaperEvent {
  return { id, time, title, detail, status }
}

function paperEventsFor(state: DecisionState): PaperEvent[] {
  const intent = event('intent', '09:49:02', '入场 intent', '$10.00 · 最高 55.0%', 'complete')
  const filled = event('filled', '09:49:04', '入场已成交', '19.84 份 · 均价 50.4%', 'complete')
  const marked = event('marked', '10:11:20', '持仓重估', '可退出价值 $12.26', 'neutral')
  const exitIntent = event('exit-intent', '10:18:08', '退出 intent', '最低退出价 63.0%', 'complete')

  if (state === 'entry_pending') return [event('intent-pending', '09:49:02', '入场 intent 等待中', '$10.00 · 尚未成交', 'pending')]
  if (state === 'missed') return [intent, event('entry-missed', '09:49:07', '入场错过', '报价升至 56.6%，未产生仓位', 'missed')]
  if (state === 'hold') return [intent, filled, marked]
  if (state === 'sell') return [intent, filled, marked, event('sell-signal', '10:17:54', 'SELL 信号', '模型下修至 57.0%', 'neutral')]
  if (state === 'exit_pending') return [intent, filled, marked, exitIntent, event('exit-pending', '10:18:09', '退出等待中', '尚未确认成交', 'pending')]
  if (state === 'exited') return [intent, filled, marked, exitIntent, event('exited', '10:18:12', '退出已成交', '$12.50 · 净 P&L +$2.50', 'complete')]
  if (state === 'exit_missed') return [intent, filled, marked, exitIntent, event('exit-missed', '10:18:14', '退出错过', '报价跌至 59.1%，仓位仍开放', 'missed')]
  if (state === 'settled') return [intent, filled, marked, event('settled', '11:42:30', '市场已结算', '$19.84 · 净 P&L +$9.84', 'complete')]
  return []
}

function hasPaperLifecycle(state: DecisionState): boolean {
  return ['entry_pending', 'missed', 'hold', 'sell', 'exit_pending', 'exited', 'exit_missed', 'settled'].includes(state)
}

export function getDecisionPreview(
  state: DecisionState,
  overlay: DecisionOverlay = 'none',
  confidence: ConfidenceState = 'high',
  selection: SelectionState = 'sinner',
): DecisionPreview {
  const numbers = numberProfile[state]
  const confidenceProfile = confidenceValues[confidence]
  const actionAvailable = overlay === 'none' && !['market_only', 'no_bet', 'wait', 'entry_pending', 'missed', 'exit_pending', 'exited', 'exit_missed', 'settled'].includes(state)
  const trajectory = baseTrajectory.map((point, index): TrajectoryPoint => {
    const isLast = index === baseTrajectory.length - 1
    const model = state === 'market_only' ? null : isLast ? numbers.model : point.model
    const market = isLast ? numbers.market : point.market
    const isGapPoint = overlay === 'gap' && index === 3
    return {
      time: point.time,
      model: isGapPoint ? null : model,
      market: isGapPoint ? null : market,
      uncertainty: model === null || isGapPoint
        ? null
        : [Math.max(0, model - confidenceProfile.spread), Math.min(1, model + confidenceProfile.spread)],
    }
  })

  const gates: DecisionGate[] = [
    {
      label: '模型覆盖',
      detail: state === 'market_only' ? '该赛事不在主巡覆盖范围' : 'ATP 主巡模型可用',
      status: state === 'market_only' ? 'fail' : 'pass',
    },
    {
      label: '数据新鲜度',
      detail: overlay === 'stale' ? '超过 45 秒阈值，撤销动作' : overlay === 'gap' ? '轨迹存在 1 个不可插值缺口' : '盘口 4 秒前 · 模型 11 秒前',
      status: overlay === 'none' ? 'pass' : 'fail',
    },
    {
      label: '市场深度',
      detail: '$10 可执行报价深度已核验',
      status: 'pass',
    },
    {
      label: '净 edge',
      detail: numbers.edge === null ? '该状态不计算 edge' : `${numbers.edge > 0 ? '+' : ''}${numbers.edge.toFixed(1)}pp`,
      status: numbers.edge !== null && numbers.edge >= 3 ? 'pass' : numbers.edge === null ? 'unknown' : 'fail',
    },
  ]

  const events = paperEventsFor(state)
  const currentExitValue = state === 'settled'
    ? 19.84
    : state === 'exited'
      ? 12.5
      : Math.round(19.84 * numbers.market * 100) / 100
  const netPnl = Math.round((currentExitValue - 10) * 100) / 100

  return {
    state,
    stateLabel: stateLabels[state],
    tone: stateTones[state],
    ...stateCopy[state],
    selection,
    selectionLabel: selection === 'sinner' ? 'Sinner 胜出' : 'Alcaraz 胜出',
    modelProbability: numbers.model,
    executableProbability: numbers.market,
    edgePp: numbers.edge,
    quoteSide: numbers.quoteSide,
    maxBuyPrice: numbers.maxBuyPrice,
    paperEv: numbers.paperEv,
    confidence,
    confidenceLabel: confidenceProfile.label,
    confidenceValue: confidenceProfile.value,
    modelVersion: 'tnx-atp-live-v3.4.1',
    dataVersion: 'p3-preview-2026-09-16.7',
    marketFreshness: overlay === 'stale' ? '最后可信报价 · 2 分 14 秒前' : overlay === 'gap' ? '报价流存在缺口 · 22 秒前' : '盘口 · 4 秒前',
    modelFreshness: overlay === 'stale' ? '最后可信模型 · 2 分 21 秒前' : '模型 · 11 秒前',
    asOf: '2026-09-16 10:18:12 澳门',
    overlay,
    actionAvailable,
    trajectory,
    gates,
    reasons: [
      'Sinner 最近 20 分接发压制率提升，结构化比赛特征为正向。',
      '盘口两侧报价独立计算；50.4% 不是对手报价的补数。',
      overlay === 'none' ? '所有 freshness gate 均在阈值内。' : '降级层覆盖基础状态，保留最后可信数字但撤销动作。',
    ],
    paper: hasPaperLifecycle(state)
      ? {
          entryCost: 10,
          averageEntry: 0.504,
          shares: 19.84,
          currentExitValue,
          netPnl,
          events,
        }
      : null,
  }
}

const pulseRows: HomePulseRow[] = [
  {
    id: 'pulse-position',
    priority: 'position',
    match: 'Jannik Sinner vs Carlos Alcaraz',
    tournament: 'ATP Finals · 半决赛',
    phase: '直播',
    modelProbability: 0.64,
    executableProbability: 0.618,
    edgePp: 2.2,
    state: 'hold',
    freshness: '4 秒前',
    stale: false,
    href: '/match?preview=p3&status=live&state=hold',
  },
  {
    id: 'pulse-buy-live',
    priority: 'buy_live',
    match: 'Aryna Sabalenka vs Coco Gauff',
    tournament: 'WTA Finals · 半决赛',
    phase: '直播',
    modelProbability: 0.671,
    executableProbability: 0.596,
    edgePp: 7.5,
    state: 'buy',
    freshness: '8 秒前',
    stale: false,
    href: '/match?preview=p3&status=live&state=buy&selection=sinner',
  },
  {
    id: 'pulse-wait-upcoming',
    priority: 'wait',
    match: 'Qinwen Zheng vs Elena Rybakina',
    tournament: 'WTA Finals · 小组赛',
    phase: '即将开始',
    modelProbability: 0.55,
    executableProbability: 0.572,
    edgePp: -2.2,
    state: 'wait',
    freshness: '12 秒前',
    stale: false,
    href: '/match?preview=p3&status=upcoming&state=wait',
  },
]

const pulsePriority: Record<HomePulseRow['priority'], number> = {
  sell: 0,
  position: 1,
  buy_live: 2,
  buy_upcoming: 3,
  wait: 4,
}

export function sortHomePulseRows(rows: HomePulseRow[]): HomePulseRow[] {
  return [...rows].sort((a, b) => pulsePriority[a.priority] - pulsePriority[b.priority]).slice(0, 3)
}

export function getHomePulseRows(state: HomePulseState): HomePulseRow[] {
  if (state === 'empty') return []
  const rows = pulseRows.map((row) => ({ ...row }))
  if (state === 'stale') {
    rows[0] = {
      ...rows[0],
      stale: true,
      freshness: '最后可信 · 2 分 14 秒前',
      href: '/match?preview=p3&status=live&state=hold&overlay=stale',
    }
  }
  return sortHomePulseRows(rows)
}

export const opportunityFixtures: OpportunityPreview[] = [
  {
    id: 'opp-sinner',
    match: 'Jannik Sinner vs Carlos Alcaraz',
    tournament: 'ATP Finals · 半决赛',
    phase: 'live',
    selection: 'Sinner 胜出',
    modelProbability: 0.64,
    executableProbability: 0.504,
    edgePp: 13.6,
    state: 'buy',
    maxBuyPrice: 0.55,
    freshness: '盘口 4 秒前 · 模型 11 秒前',
    stale: false,
    href: '/match?preview=p3&status=live&state=buy',
  },
  {
    id: 'opp-sabalenka',
    match: 'Aryna Sabalenka vs Coco Gauff',
    tournament: 'WTA Finals · 半决赛',
    phase: 'live',
    selection: 'Sabalenka 胜出',
    modelProbability: 0.671,
    executableProbability: 0.596,
    edgePp: 7.5,
    state: 'buy',
    maxBuyPrice: 0.61,
    freshness: '盘口 8 秒前 · 模型 14 秒前',
    stale: false,
    href: '/match?preview=p3&status=live&state=buy&selection=sinner',
  },
  {
    id: 'opp-zheng',
    match: 'Qinwen Zheng vs Elena Rybakina',
    tournament: 'WTA Finals · 小组赛',
    phase: 'upcoming',
    selection: 'Zheng 胜出',
    modelProbability: 0.55,
    executableProbability: 0.572,
    edgePp: -2.2,
    state: 'wait',
    maxBuyPrice: 0.54,
    freshness: '盘口 12 秒前 · 模型 19 秒前',
    stale: false,
    href: '/match?preview=p3&status=upcoming&state=wait',
  },
]

export const marketListingFixtures: MarketListingPreview[] = [
  {
    id: 'market-sinner',
    match: 'Jannik Sinner vs Carlos Alcaraz',
    tournament: 'ATP Finals · 半决赛',
    tier: 'main',
    gender: 'men',
    phase: 'live',
    covered: true,
    state: 'no_bet',
    playerOne: 'Sinner',
    playerTwo: 'Alcaraz',
    playerOneAsk: 0.504,
    playerTwoAsk: 0.508,
    spread: 0.012,
    depth: 420,
    modelProbability: 0.52,
    reason: '净 edge +1.6pp，低于 3.0pp hard gate',
    freshness: '4 秒前',
    stale: false,
    href: '/match?preview=p3&status=live&state=no_bet',
  },
  {
    id: 'market-zheng',
    match: 'Qinwen Zheng vs Elena Rybakina',
    tournament: 'WTA Finals · 小组赛',
    tier: 'main',
    gender: 'women',
    phase: 'upcoming',
    covered: true,
    state: 'no_bet',
    playerOne: 'Zheng',
    playerTwo: 'Rybakina',
    playerOneAsk: 0.572,
    playerTwoAsk: 0.447,
    spread: 0.019,
    depth: 238,
    modelProbability: 0.55,
    reason: '当前价高于 54.0% 最高可买价',
    freshness: '12 秒前',
    stale: false,
    href: '/match?preview=p3&status=upcoming&state=no_bet',
  },
  {
    id: 'market-challenger',
    match: 'Eliot Spizzirri vs Zizou Bergs',
    tournament: 'Phoenix Challenger · 决赛',
    tier: 'challenger',
    gender: 'men',
    phase: 'live',
    covered: false,
    state: 'market_only',
    playerOne: 'Spizzirri',
    playerTwo: 'Bergs',
    playerOneAsk: 0.481,
    playerTwoAsk: 0.542,
    spread: 0.023,
    depth: 96,
    modelProbability: null,
    reason: 'Challenger 暂无模型覆盖',
    freshness: '21 秒前',
    stale: false,
    href: '/match?preview=p3&status=live&state=market_only',
  },
  {
    id: 'market-itf',
    match: 'Maya Tanaka vs Clara Novak',
    tournament: 'ITF W75 · 半决赛',
    tier: 'itf',
    gender: 'women',
    phase: 'upcoming',
    covered: false,
    state: 'market_only',
    playerOne: 'Tanaka',
    playerTwo: 'Novak',
    playerOneAsk: 0.461,
    playerTwoAsk: 0.566,
    spread: 0.027,
    depth: 54,
    modelProbability: null,
    reason: 'ITF 暂无模型覆盖',
    freshness: '39 秒前',
    stale: true,
    href: '/match?preview=p3&status=upcoming&state=market_only&overlay=stale',
  },
  {
    id: 'market-other',
    match: 'Team Europe vs Team World',
    tournament: 'Exhibition · 第 3 场',
    tier: 'other',
    gender: 'men',
    phase: 'upcoming',
    covered: false,
    state: 'market_only',
    playerOne: 'Europe',
    playerTwo: 'World',
    playerOneAsk: 0.614,
    playerTwoAsk: 0.413,
    spread: 0.027,
    depth: 71,
    modelProbability: null,
    reason: '表演赛不进入模型覆盖',
    freshness: '18 秒前',
    stale: false,
    href: '/match?preview=p3&status=upcoming&state=market_only',
  },
]

export const openPaperFixtures: PaperLedgerPreview[] = [
  {
    id: 'paper-open',
    match: 'Jannik Sinner vs Carlos Alcaraz',
    tournament: 'ATP Finals · 半决赛',
    direction: 'Sinner 胜出',
    state: 'hold',
    cost: 10,
    shares: 19.84,
    averageEntry: 0.504,
    currentExitValue: 12.26,
    netPnl: 2.26,
    freshness: '4 秒前',
    detail: '开放仓位 · 当前建议 HOLD',
    href: '/match?preview=p3&status=live&state=hold',
  },
  {
    id: 'paper-pending',
    match: 'Aryna Sabalenka vs Coco Gauff',
    tournament: 'WTA Finals · 半决赛',
    direction: 'Sabalenka 胜出',
    state: 'entry_pending',
    cost: 10,
    shares: 0,
    averageEntry: 0.596,
    currentExitValue: null,
    netPnl: null,
    freshness: '等待 6 秒',
    detail: '入场 intent 等待报价确认 · 尚未成交',
    href: '/match?preview=p3&status=live&state=entry_pending',
  },
  {
    id: 'paper-resolution',
    match: 'Qinwen Zheng vs Elena Rybakina',
    tournament: 'WTA Finals · 小组赛',
    direction: 'Zheng 胜出',
    state: 'exit_pending',
    cost: 10,
    shares: 18.52,
    averageEntry: 0.54,
    currentExitValue: 11.48,
    netPnl: 1.48,
    freshness: '等待 9 秒',
    detail: '退出 intent 等待确认 · 仓位仍开放',
    href: '/match?preview=p3&status=live&state=exit_pending',
  },
]

export const terminalPaperFixtures: PaperLedgerPreview[] = [
  {
    id: 'paper-exited',
    match: 'Jannik Sinner vs Carlos Alcaraz',
    tournament: 'ATP Finals · 半决赛',
    direction: 'Sinner 胜出',
    state: 'exited',
    cost: 10,
    shares: 19.84,
    averageEntry: 0.504,
    currentExitValue: 12.5,
    netPnl: 2.5,
    freshness: '18 分钟前',
    detail: 'EV exit · 63.0% 退出',
    href: '/match?preview=p3&status=finished&state=exited',
  },
  {
    id: 'paper-missed',
    match: 'Qinwen Zheng vs Elena Rybakina',
    tournament: 'WTA Finals · 小组赛',
    direction: 'Zheng 胜出',
    state: 'missed',
    cost: 10,
    shares: 0,
    averageEntry: 0.54,
    currentExitValue: null,
    netPnl: 0,
    freshness: '1 小时前',
    detail: '入场报价跳离上限 · 未产生仓位',
    href: '/match?preview=p3&status=upcoming&state=missed',
  },
  {
    id: 'paper-settled-positive',
    match: 'Aryna Sabalenka vs Coco Gauff',
    tournament: 'WTA Finals · 半决赛',
    direction: 'Sabalenka 胜出',
    state: 'settled',
    cost: 10,
    shares: 17.24,
    averageEntry: 0.58,
    currentExitValue: 17.24,
    netPnl: 7.24,
    freshness: '昨天',
    detail: 'HODL · 胜出结算',
    href: '/match?preview=p3&status=finished&state=settled',
  },
  {
    id: 'paper-settled-negative',
    match: 'Taylor Fritz vs Alexander Zverev',
    tournament: 'ATP Finals · 小组赛',
    direction: 'Fritz 胜出',
    state: 'settled',
    cost: 10,
    shares: 18.18,
    averageEntry: 0.55,
    currentExitValue: 0,
    netPnl: -10,
    freshness: '2 天前',
    detail: 'HODL · 方向落败',
    href: '/match?preview=p3&status=finished&state=settled&selection=alcaraz',
  },
  {
    id: 'paper-settled-void',
    match: 'Novak Djokovic vs Alex de Minaur',
    tournament: 'Paris Masters · 四分之一决赛',
    direction: 'Djokovic 胜出',
    state: 'settled',
    cost: 10,
    shares: 20,
    averageEntry: 0.5,
    currentExitValue: 10,
    netPnl: 0,
    freshness: '3 天前',
    detail: '退赛规则 · 50–50 结算',
    href: '/match?preview=p3&status=finished&state=settled',
  },
]

function normalizeQueryValue(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value
}

export function parseDecisionState(value: string | string[] | undefined): DecisionState {
  const raw = normalizeQueryValue(value)?.toLowerCase().replaceAll('-', '_')
  if (raw === 'filled') return 'hold'
  return DECISION_STATES.includes(raw as DecisionState) ? raw as DecisionState : 'buy'
}

export function parseDecisionOverlay(value: string | string[] | undefined): DecisionOverlay {
  const raw = normalizeQueryValue(value)
  return raw === 'stale' || raw === 'gap' ? raw : 'none'
}

export function parseConfidenceState(value: string | string[] | undefined): ConfidenceState {
  const raw = normalizeQueryValue(value)
  return ['high', 'medium', 'low', 'empty', 'error'].includes(raw ?? '') ? raw as ConfidenceState : 'high'
}

export function parseAnalysisState(value: string | string[] | undefined): AnalysisState {
  return normalizeQueryValue(value) === 'collapsed' ? 'collapsed' : 'expanded'
}

export function parseSelectionState(value: string | string[] | undefined): SelectionState {
  return normalizeQueryValue(value) === 'alcaraz' ? 'alcaraz' : 'sinner'
}

export function parseMethodologyState(value: string | string[] | undefined): MethodologyState {
  return normalizeQueryValue(value) === 'open' ? 'open' : 'closed'
}

export function parseHomePulseState(value: string | string[] | undefined): HomePulseState {
  const raw = normalizeQueryValue(value)?.toLowerCase().replaceAll('-', '_')
  if (raw === 'open_stale') return 'stale'
  return raw === 'stale' || raw === 'empty' ? raw : 'populated'
}

export function parseMarketView(value: string | string[] | undefined): MarketView {
  const raw = normalizeQueryValue(value)
  return raw === 'all' || raw === 'paper' ? raw : 'opportunities'
}

export function parseMarketsState(value: string | string[] | undefined): MarketsPreviewState {
  const raw = normalizeQueryValue(value)?.toLowerCase().replaceAll('-', '_')
  const values: MarketsPreviewState[] = ['populated', 'empty', 'partial_stale', 'filtered_empty', 'supplier_empty', 'open', 'terminal', 'resolution_pending', 'error']
  return values.includes(raw as MarketsPreviewState) ? raw as MarketsPreviewState : 'populated'
}

export function parseTierFilters(value: string | string[] | undefined): TourTier[] {
  const raw = Array.isArray(value) ? value : value ? [value] : []
  return raw.filter((item): item is TourTier => ['main', 'challenger', 'itf', 'other'].includes(item))
}

export function parseGenderFilter(value: string | string[] | undefined): MarketGender | 'all' {
  const raw = normalizeQueryValue(value)
  return raw === 'men' || raw === 'women' ? raw : 'all'
}

export function parsePhaseFilter(value: string | string[] | undefined): MatchPhase | 'all' {
  const raw = normalizeQueryValue(value)
  return raw === 'live' || raw === 'upcoming' ? raw : 'all'
}

export function filterMarketListings(
  listings: MarketListingPreview[],
  tiers: TourTier[],
  gender: MarketGender | 'all',
  phase: MatchPhase | 'all',
): MarketListingPreview[] {
  return listings.filter((listing) =>
    (tiers.length === 0 || tiers.includes(listing.tier)) &&
    (gender === 'all' || listing.gender === gender) &&
    (phase === 'all' || listing.phase === phase),
  )
}
