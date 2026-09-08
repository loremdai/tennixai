export type ProductPhase = 'p1' | 'p2' | 'p3'
export type MatchStatus = 'upcoming' | 'live' | 'finished'
export type MatchHighlight = 'server' | 'serve-stats' | 'score' | 'momentum' | null

const SET_NUMERALS = ['一', '二', '三', '四', '五']

export function setLabel(index: number): string {
  return `第${SET_NUMERALS[index] ?? index + 1}盘`
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
