export type MatchStatus = 'upcoming' | 'live' | 'finished'
export type MatchHighlight = 'server' | 'serve-stats' | 'score' | 'momentum' | null

const SET_NUMERALS = ['一', '二', '三', '四', '五']

export function setLabel(index: number): string {
  return `第${SET_NUMERALS[index] ?? index + 1}盘`
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
    description: '实时比分、发球方与技术统计',
  },
  finished: {
    short: '完赛',
    title: '比赛已结束',
    description: '最终比分、时长与比赛总结',
  },
}
