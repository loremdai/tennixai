export type UserFacingErrorSurface = 'assistant' | 'match' | 'schedule' | 'market' | 'player'

const fallbackBySurface: Record<UserFacingErrorSurface, string> = {
  assistant: 'AI 助手暂时无法回答，请稍后重试。',
  match: '比赛详情暂时无法加载，请稍后重试。',
  schedule: '比赛信息暂时无法加载，请稍后重试。',
  market: '市场数据暂时无法加载，请稍后重试。',
  player: '球员资料暂时无法加载，请稍后重试。',
}

export function userFacingApiError(
  code: string | null | undefined,
  surface: UserFacingErrorSurface,
): string {
  if (code === 'rate_limited') return '请求过于频繁，请稍后再试。'
  if (code === 'p3_disabled' && surface === 'market') {
    return '市场功能暂未开放；比赛和球员信息仍可正常使用。'
  }
  if (code === 'provider_unavailable' && surface === 'market') {
    return '行情来源暂时不可用，请稍后重试。'
  }
  return fallbackBySurface[surface]
}
