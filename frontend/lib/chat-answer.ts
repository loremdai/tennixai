import type { StructuredData } from '@/lib/api/types'

type ChatAnswerState = {
  data: StructuredData | null
  error: { code: string } | null
}

export type ChatAnswerScope = 'global' | 'match'

export function getChatAnswerLabel(chat: ChatAnswerState, scope: ChatAnswerScope): string {
  if (chat.error) return '查询未完成'

  switch (chat.data?.kind) {
    case 'match':
      return scope === 'match' ? '本场比赛结构化结果' : '当前比赛'
    case 'unsupported':
      return '暂不支持'
    case 'matches':
      return scope === 'match' ? '本场比赛结构化结果' : '结构化比赛结果'
    case 'intelligence':
      return '本场比赛分析'
    default:
      return scope === 'match' ? '本场比赛结构化结果' : '回答'
  }
}
