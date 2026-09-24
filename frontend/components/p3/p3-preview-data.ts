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
  confidence: ConfidenceState
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
    eyebrow: '仅显示市场报价',
    title: '该赛事暂不提供模型估算',
    description: '这里仍可查看两位球员的市场报价。',
    reason: '目前没有适用于这类比赛的模型。',
  },
  no_bet: {
    eyebrow: '暂不建议模拟买入',
    title: '模型与市场价格差距不明显',
    description: '扣除交易成本后，目前没有明显优势。',
    reason: '模型估算胜率与市场价格接近。',
  },
  wait: {
    eyebrow: '等待更合适的价格',
    title: '可以关注，但当前价格偏高',
    description: '价格回落到 55.0% 或以下时，可以重新评估。',
    reason: '当前模拟买入均价高于参考价。',
  },
  buy: {
    eyebrow: '模拟买入机会',
    title: 'Sinner 出现模拟买入机会',
    description: '模型估算胜率 64.0%，10 美元模拟买入均价 50.4%，估算优势 +13.6 个百分点。',
    reason: '比赛数据和市场价格均符合当前评估条件。',
  },
  entry_pending: {
    eyebrow: '等待成交确认',
    title: '模拟买入已提交，尚未成交',
    description: '正在确认市场是否能按预期价格和金额成交。',
    reason: '确认完成前，暂不计为已买入。',
  },
  missed: {
    eyebrow: '模拟买入未成交',
    title: '价格已超出预期，本次没有买入',
    description: '价格在确认前升至 56.6%，高于预期的 55.0%。',
    reason: '没有建立模拟持仓。',
  },
  hold: {
    eyebrow: '模拟持仓进行中',
    title: '模拟持仓中',
    description: '买入均价 50.4%，当前模拟卖出价格 61.8%。',
    reason: '当前模型估算胜率为 64.0%。',
  },
  sell: {
    eyebrow: '模拟退出机会',
    title: '出现模拟退出机会',
    description: '当前模拟卖出价格为 64.2%，模型估算胜率为 57.0%。',
    reason: '模型估算与市场价格出现明显差异。',
  },
  exit_pending: {
    eyebrow: '等待退出确认',
    title: '模拟退出已提交，持仓仍然开放',
    description: '正在确认是否能按预期价格卖出。',
    reason: '确认完成前，仍按持仓中显示。',
  },
  exited: {
    eyebrow: '模拟持仓已退出',
    title: '模拟持仓已退出',
    description: '退出价值 $12.50，模拟盈亏为 +$2.50。',
    reason: '模拟退出已确认，记录已保留。',
  },
  exit_missed: {
    eyebrow: '模拟退出未成交',
    title: '本次没有卖出，模拟持仓仍然开放',
    description: '市场价格在确认前跌至 59.1%，低于预期的 63.0%。',
    reason: '模拟持仓仍在进行。',
  },
  settled: {
    eyebrow: '模拟记录已结算',
    title: 'Sinner 获胜，模拟记录已结算',
    description: '最终模拟盈亏为 +$9.84。',
    reason: '模拟结果已按比赛最终赛果记录。',
  },
}

const confidenceValues: Record<ConfidenceState, { spread: number }> = {
  high: { spread: 0.035 },
  medium: { spread: 0.055 },
  low: { spread: 0.09 },
  empty: { spread: 0.12 },
  error: { spread: 0.12 },
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
}> = {
  market_only: { model: null, market: 0.504, edge: null, quoteSide: 'market', maxBuyPrice: null },
  no_bet: { model: 0.52, market: 0.504, edge: 1.6, quoteSide: 'ask', maxBuyPrice: null },
  wait: { model: 0.64, market: 0.572, edge: 6.8, quoteSide: 'ask', maxBuyPrice: 0.55 },
  buy: { model: 0.64, market: 0.504, edge: 13.6, quoteSide: 'ask', maxBuyPrice: 0.55 },
  entry_pending: { model: 0.64, market: 0.504, edge: 13.6, quoteSide: 'ask', maxBuyPrice: 0.55 },
  missed: { model: 0.64, market: 0.566, edge: 7.4, quoteSide: 'ask', maxBuyPrice: 0.55 },
  hold: { model: 0.64, market: 0.618, edge: 2.2, quoteSide: 'bid', maxBuyPrice: null },
  sell: { model: 0.57, market: 0.642, edge: -7.2, quoteSide: 'bid', maxBuyPrice: null },
  exit_pending: { model: 0.57, market: 0.63, edge: -6, quoteSide: 'bid', maxBuyPrice: null },
  exited: { model: 0.57, market: 0.63, edge: -6, quoteSide: 'bid', maxBuyPrice: null },
  exit_missed: { model: 0.57, market: 0.591, edge: -2.1, quoteSide: 'bid', maxBuyPrice: null },
  settled: { model: 0.91, market: 1, edge: null, quoteSide: 'market', maxBuyPrice: null },
}

function event(id: string, time: string, title: string, detail: string, status: PaperEvent['status']): PaperEvent {
  return { id, time, title, detail, status }
}

function paperEventsFor(state: DecisionState): PaperEvent[] {
  const intent = event('intent', '09:49:02', '已提交模拟买入', '$10.00 · 参考价 55.0%', 'complete')
  const filled = event('filled', '09:49:04', '模拟买入已成交', '19.84 份 · 均价 50.4%', 'complete')
  const marked = event('marked', '10:11:20', '持仓价值更新', '当前可卖出价值 $12.26', 'neutral')
  const exitIntent = event('exit-intent', '10:18:08', '已提交模拟退出', '参考卖出价 63.0%', 'complete')

  if (state === 'entry_pending') return [event('intent-pending', '09:49:02', '等待模拟买入确认', '$10.00 · 尚未成交', 'pending')]
  if (state === 'missed') return [intent, event('entry-missed', '09:49:07', '模拟买入未成交', '报价升至 56.6%，未建立持仓', 'missed')]
  if (state === 'hold') return [intent, filled, marked]
  if (state === 'sell') return [intent, filled, marked, event('sell-signal', '10:17:54', '出现模拟退出机会', '模型估算胜率下调至 57.0%', 'neutral')]
  if (state === 'exit_pending') return [intent, filled, marked, exitIntent, event('exit-pending', '10:18:09', '等待模拟退出确认', '尚未确认成交', 'pending')]
  if (state === 'exited') return [intent, filled, marked, exitIntent, event('exited', '10:18:12', '模拟退出已成交', '$12.50 · 模拟盈亏 +$2.50', 'complete')]
  if (state === 'exit_missed') return [intent, filled, marked, exitIntent, event('exit-missed', '10:18:14', '模拟退出未成交', '报价跌至 59.1%，持仓仍开放', 'missed')]
  if (state === 'settled') return [intent, filled, marked, event('settled', '11:42:30', '比赛结果已结算', '$19.84 · 模拟盈亏 +$9.84', 'complete')]
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
      label: '赛事范围',
      detail: state === 'market_only' ? '暂不提供胜率估算' : '可提供胜率估算',
      status: state === 'market_only' ? 'fail' : 'pass',
    },
    {
      label: '数据更新情况',
      detail: overlay === 'stale' ? '报价更新较慢，已暂停新的模拟操作' : overlay === 'gap' ? '比赛数据更新中断，已暂停新的模拟操作' : '报价 4 秒前 · 胜率估算 11 秒前',
      status: overlay === 'none' ? 'pass' : 'fail',
    },
    {
      label: '可交易金额',
      detail: '10 美元模拟金额可成交',
      status: 'pass',
    },
    {
      label: '模型与市场差距',
      detail: numbers.edge === null ? '暂不可计算' : `${numbers.edge > 0 ? '+' : ''}${numbers.edge.toFixed(1)} 个百分点`,
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
    confidence,
    modelVersion: 'tnx-atp-live-v3.4.1',
    dataVersion: 'p3-preview-2026-09-16.7',
    marketFreshness: overlay === 'stale' ? '报价更新较慢 · 2 分 14 秒前' : overlay === 'gap' ? '报价中断 · 22 秒前' : '报价更新 · 4 秒前',
    modelFreshness: overlay === 'stale' ? '胜率估算更新 · 2 分 21 秒前' : '胜率估算更新 · 11 秒前',
    asOf: '2026-09-16 10:18:12 北京',
    overlay,
    actionAvailable,
    trajectory,
    gates,
    reasons: [
      'Sinner 最近 20 分接发压制率提升，模型对其胜率的估算随之变化。',
      '买入价与卖出价分别计算，不能简单相加为 100%。',
      overlay === 'none' ? '比赛和市场数据均及时。' : '报价或实时数据暂不可用，已暂停新的模拟操作。',
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
      freshness: '上次有效报价 · 2 分 14 秒前',
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
    reason: '模型与市场差距较小，暂不建议模拟买入',
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
    reason: '当前买入价高于模型可接受范围',
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
    reason: '挑战赛暂不提供胜率估算',
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
    reason: 'ITF 赛事暂不提供胜率估算',
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
    reason: '表演赛暂不提供胜率估算',
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
