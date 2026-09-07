export type ProductPhase = 'p1' | 'p2' | 'p3'
export type MatchStatus = 'upcoming' | 'live' | 'finished'
export type MatchHighlight = 'server' | 'serve-stats' | 'score' | 'momentum' | null

export type Player = {
  id: string
  name: string
  shortName: string
  initials: string
  country: string
  countryCode: string
  flagUrl: string
  rank: number
  seed: number
}

export type MatchScoreRow = {
  playerId: Player['id']
  sets: number[]
  points?: string
  serving?: boolean
  winner?: boolean
}

export const phaseLabels: Record<
  ProductPhase,
  { short: string; title: string; description: string }
> = {
  p1: {
    short: 'P1 · 信息',
    title: '赛前信息助手',
    description: '赛程、背景与结构化问答',
  },
  p2: {
    short: 'P2 · 实时',
    title: '实时比赛智能',
    description: '比分、技术统计与动量',
  },
  p3: {
    short: 'P3 · 决策',
    title: '市场决策智能',
    description: '模型、市场与价值判断',
  },
}

export const matchStatusLabels: Record<
  MatchStatus,
  { short: string; title: string; description: string }
> = {
  upcoming: {
    short: '赛前',
    title: '即将开始',
    description: '赛程、场地与对阵背景',
  },
  live: {
    short: '直播',
    title: '比赛进行中',
    description: '比分、发球方与 P2 技术预览',
  },
  finished: {
    short: '完赛',
    title: '比赛已结束',
    description: '最终比分、时长与比赛总结',
  },
}

export const players: [Player, Player] = [
  {
    id: 'jannik-sinner',
    name: 'Jannik Sinner',
    shortName: 'Sinner',
    initials: 'JS',
    country: '意大利',
    countryCode: 'ITA',
    flagUrl: 'https://flagcdn.com/w40/it.png',
    rank: 1,
    seed: 1,
  },
  {
    id: 'carlos-alcaraz',
    name: 'Carlos Alcaraz',
    shortName: 'Alcaraz',
    initials: 'CA',
    country: '西班牙',
    countryCode: 'ESP',
    flagUrl: 'https://flagcdn.com/w40/es.png',
    rank: 2,
    seed: 2,
  },
]

export const matchMeta = {
  tournament: 'ATP Finals',
  event: '男单半决赛',
  round: '半决赛',
  surface: '室内硬地',
  venue: 'Inalpi Arena',
  location: '都灵，意大利',
  court: '中央球场',
  scheduledDate: '今天',
  scheduledTime: '20:30',
  timezone: 'CET · 本地时间',
  format: '三盘两胜 · BO3',
  liveElapsed: '2 小时 12 分',
  finalDuration: '2 小时 28 分',
  currentSet: 3,
  currentGame: 10,
}

export const liveScore: { rows: [MatchScoreRow, MatchScoreRow] } = {
  rows: [
    {
      playerId: 'jannik-sinner',
      sets: [6, 4, 4],
      points: '30',
      serving: true,
    },
    {
      playerId: 'carlos-alcaraz',
      sets: [4, 6, 5],
      points: '15',
    },
  ],
}

export const finishedScore: { rows: [MatchScoreRow, MatchScoreRow] } = {
  rows: [
    {
      playerId: 'jannik-sinner',
      sets: [6, 4, 6],
      winner: true,
    },
    {
      playerId: 'carlos-alcaraz',
      sets: [4, 6, 3],
    },
  ],
}

export const matchStats = [
  { label: '一发成功率', sinner: '68%', alcaraz: '61%', sinnerShare: 53 },
  { label: '一发得分率', sinner: '79%', alcaraz: '67%', sinnerShare: 54 },
  { label: 'ACE 球', sinner: '8', alcaraz: '5', sinnerShare: 62 },
  { label: '双误', sinner: '2', alcaraz: '4', sinnerShare: 33 },
  { label: '破发点兑现', sinner: '3/6', alcaraz: '2/5', sinnerShare: 56 },
] as const

export const momentumData = [
  { point: '第二盘 4–4', momentum: -8 },
  { point: '第二盘 5–4', momentum: -5 },
  { point: '第二盘 6–4', momentum: -12 },
  { point: '第三盘 0–1', momentum: -7 },
  { point: '第三盘 1–1', momentum: 1 },
  { point: '第三盘 2–2', momentum: 5 },
  { point: '第三盘 3–2', momentum: 13 },
  { point: '第三盘 3–3', momentum: 8 },
  { point: '第三盘 4–5', momentum: 12 },
  { point: '当前', momentum: 14 },
] as const

export const recentPoints = [
  {
    score: '30–15',
    player: 'Sinner',
    detail: '外角 ACE，时速 203 km/h',
  },
  {
    score: '15–15',
    player: 'Alcaraz',
    detail: '反拍直线制胜分',
  },
  {
    score: '15–0',
    player: 'Sinner',
    detail: '一发后第三拍正手得分',
  },
  {
    score: '4–5',
    player: 'Alcaraz',
    detail: '守住发球局，Sinner 将发球留在本盘',
  },
] as const

export function getPlayer(playerId: Player['id']) {
  return players.find((player) => player.id === playerId) ?? players[0]
}
