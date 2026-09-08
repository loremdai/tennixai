import type { MatchScoreDto } from '@/lib/api/types'
import type { MatchViewModel } from '@/lib/view-models'
import type { MatchHighlight, MatchStatus } from './match-data'

export type PreviewPlayer = {
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

export type PreviewScoreRow = {
  playerId: PreviewPlayer['id']
  sets: number[]
  points?: string
  serving?: boolean
  winner?: boolean
}

export const previewPlayers: [PreviewPlayer, PreviewPlayer] = [
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

export const previewMatchMeta = {
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

export const previewLiveScore: { rows: [PreviewScoreRow, PreviewScoreRow] } = {
  rows: [
    { playerId: 'jannik-sinner', sets: [6, 4, 4], points: '30', serving: true },
    { playerId: 'carlos-alcaraz', sets: [4, 6, 5], points: '15' },
  ],
}

export const previewFinishedScore: { rows: [PreviewScoreRow, PreviewScoreRow] } = {
  rows: [
    { playerId: 'jannik-sinner', sets: [6, 4, 6], winner: true },
    { playerId: 'carlos-alcaraz', sets: [4, 6, 3] },
  ],
}

export const previewMatchStats = [
  { label: '一发成功率', sinner: '68%', alcaraz: '61%', sinnerShare: 53 },
  { label: '一发得分率', sinner: '79%', alcaraz: '67%', sinnerShare: 54 },
  { label: 'ACE 球', sinner: '8', alcaraz: '5', sinnerShare: 62 },
  { label: '双误', sinner: '2', alcaraz: '4', sinnerShare: 33 },
  { label: '破发点兑现', sinner: '3/6', alcaraz: '2/5', sinnerShare: 56 },
] as const

export const previewMomentumData = [
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

export const previewRecentPoints = [
  { score: '30–15', player: 'Sinner', detail: '外角 ACE，时速 203 km/h' },
  { score: '15–15', player: 'Alcaraz', detail: '反拍直线制胜分' },
  { score: '15–0', player: 'Sinner', detail: '一发后第三拍正手得分' },
  { score: '4–5', player: 'Alcaraz', detail: '守住发球局，Sinner 将发球留在本盘' },
] as const

export function getPreviewPlayer(playerId: PreviewPlayer['id']) {
  return previewPlayers.find((player) => player.id === playerId) ?? previewPlayers[0]
}

export function buildPreviewMatch(status: MatchStatus): MatchViewModel {
  const liveScoreDto: MatchScoreDto = {
    sets_won: [1, 1],
    sets: [
      { number: 1, player1_games: 6, player2_games: 4 },
      { number: 2, player1_games: 4, player2_games: 6 },
      { number: 3, player1_games: 4, player2_games: 5 },
    ],
    points: ['30', '15'],
    is_tiebreak: false,
  }
  const finishedScoreDto: MatchScoreDto = {
    sets_won: [2, 1],
    sets: [
      { number: 1, player1_games: 6, player2_games: 4 },
      { number: 2, player1_games: 4, player2_games: 6 },
      { number: 3, player1_games: 6, player2_games: 3 },
    ],
    points: [null, null],
    is_tiebreak: false,
  }

  return {
    id: 'preview-match',
    canonicalStatus: status === 'upcoming' ? 'scheduled' : status,
    visualStatus: status,
    tournament: previewMatchMeta.tournament,
    round: previewMatchMeta.round,
    surface: previewMatchMeta.surface,
    scheduledDate: previewMatchMeta.scheduledDate,
    scheduledTime: previewMatchMeta.scheduledTime,
    timezoneLabel: '澳门时间',
    format: previewMatchMeta.format,
    indoorLabel: '室内',
    players: [
      {
        id: previewPlayers[0].id,
        name: previewPlayers[0].name,
        shortName: previewPlayers[0].shortName,
        initials: previewPlayers[0].initials,
        countryCode: previewPlayers[0].countryCode,
        ranking: previewPlayers[0].rank,
      },
      {
        id: previewPlayers[1].id,
        name: previewPlayers[1].name,
        shortName: previewPlayers[1].shortName,
        initials: previewPlayers[1].initials,
        countryCode: previewPlayers[1].countryCode,
        ranking: previewPlayers[1].rank,
      },
    ],
    score: status === 'live' ? liveScoreDto : status === 'finished' ? finishedScoreDto : null,
    serverPlayerId: status === 'live' ? previewPlayers[0].id : null,
    winnerPlayerId: status === 'finished' ? previewPlayers[0].id : null,
    freshnessLabel: '预览数据',
    isStale: false,
  }
}

export type PreviewAnswer = {
  label: string
  question: string
  answer: string
  highlight?: Exclude<MatchHighlight, null>
  metrics?: Array<{ label: string; value: string }>
}

export function previewAnswerQuestion(question: string, status: MatchStatus): PreviewAnswer {
  const normalized = question.trim().toLowerCase()

  if (status === 'upcoming') {
    if (normalized.includes('几点') || normalized.includes('时间') || normalized.includes('start')) {
      return {
        label: '开赛时间',
        question,
        answer: '本场比赛计划于今天 20:30 开始，地点是都灵 Inalpi Arena。若前一场比赛延长，时间会自动更新。',
      }
    }

    if (normalized.includes('赛事') || normalized.includes('tournament')) {
      return {
        label: '赛事信息',
        question,
        answer: '这是 ATP Finals 男单比赛，也是赛季末最重要的室内硬地赛事之一。',
      }
    }

    if (normalized.includes('轮') || normalized.includes('round')) {
      return {
        label: '比赛轮次',
        question,
        answer: '这是男单半决赛，胜者将进入 ATP Finals 决赛。',
      }
    }

    if (normalized.includes('场地') || normalized.includes('surface') || normalized.includes('硬地')) {
      return {
        label: '场地信息',
        question,
        answer: '比赛将在室内硬地进行。具体球场尚未公布，开赛前会自动补全。',
      }
    }

    return {
      label: '赛前上下文',
      question,
      answer: 'Sinner 与 Alcaraz 将于今天 20:30 在都灵进行 ATP Finals 半决赛，赛制为三盘两胜。',
    }
  }

  if (status === 'live') {
    if (
      normalized.includes('发球表现') ||
      normalized.includes('一发') ||
      normalized.includes('serving')
    ) {
      return {
        label: '发球表现',
        question,
        answer: 'Sinner 目前的一发表现更强：一发成功率 68%，一发得分率 79%，并已发出 8 记 ACE。',
        highlight: 'serve-stats',
        metrics: [
          { label: '一发成功率', value: '68%' },
          { label: '一发得分率', value: '79%' },
          { label: 'ACE 球', value: '8' },
        ],
      }
    }

    if (normalized.includes('谁') && normalized.includes('发球')) {
      return { label: '当前发球方', question, answer: 'Sinner 正在发球。', highlight: 'server' }
    }

    if (normalized.includes('比分') || normalized.includes('score')) {
      return {
        label: '实时比分',
        question,
        answer: '比赛进入第三盘，Alcaraz 以 5–4 领先；当前局分 30–15，Sinner 发球。',
        highlight: 'score',
      }
    }

    if (normalized.includes('第一盘') || normalized.includes('first set')) {
      return {
        label: '盘分回顾',
        question,
        answer: 'Sinner 以 6–4 赢下第一盘，Alcaraz 随后以 6–4 扳回第二盘。',
        highlight: 'score',
      }
    }

    if (normalized.includes('动量') || normalized.includes('momentum') || normalized.includes('变化')) {
      return {
        label: '比赛动量',
        question,
        answer: '动量轻微转向 Sinner。他在最近 7 个短回合中赢下 5 分，但仍需要守住这个发球局。',
        highlight: 'momentum',
      }
    }

    return {
      label: '实时上下文',
      question,
      answer: '当前是第三盘，Alcaraz 以 5–4 领先，Sinner 正在发球。你还可以询问比分、发球或动量。',
      highlight: 'score',
    }
  }

  if (normalized.includes('谁赢') || normalized.includes('winner')) {
    return { label: '比赛结果', question, answer: 'Jannik Sinner 赢得了这场比赛。', highlight: 'score' }
  }

  if (normalized.includes('比分') || normalized.includes('score')) {
    return {
      label: '最终比分',
      question,
      answer: 'Sinner 以 6–4、4–6、6–3 击败 Alcaraz。',
      highlight: 'score',
    }
  }

  if (normalized.includes('多久') || normalized.includes('时长') || normalized.includes('long')) {
    return { label: '比赛时长', question, answer: '比赛持续了 2 小时 28 分。' }
  }

  return {
    label: '比赛总结',
    question,
    answer: 'Sinner 赢下第一盘后被 Alcaraz 扳平，随后凭借决胜盘更稳定的一发和一次关键破发，以 6–3 锁定胜局。',
    highlight: 'score',
  }
}

export const previewPromptsByStatus: Record<MatchStatus, string[]> = {
  upcoming: ['这场比赛几点开始？', '这是什么赛事？', '现在进行到哪一轮？', '比赛是什么场地？'],
  live: ['现在谁在发球？', '当前比分是多少？', '谁赢了第一盘？', 'Sinner 发球表现如何？', '比赛动量改变了吗？'],
  finished: ['谁赢了？', '最终比分是多少？', '比赛持续了多久？', '总结这场比赛'],
}

export const previewContextDescriptions: Record<MatchStatus, string> = {
  upcoming: '已锁定本场赛程与对阵背景',
  live: '与当前比分和技术统计同步',
  finished: '基于最终比分与赛后数据',
}
