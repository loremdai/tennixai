import { describe, expect, it } from 'vitest'

import { userFacingApiError } from '@/lib/api/user-facing-errors'

describe('user-facing API errors', () => {
  it('translates internal and upstream failures into ordinary language', () => {
    expect(userFacingApiError('internal_error', 'match')).toBe('比赛详情暂时无法加载，请稍后重试。')
    expect(userFacingApiError('provider_unavailable', 'schedule')).toBe('比赛信息暂时无法加载，请稍后重试。')
    expect(userFacingApiError('llm_unavailable', 'assistant')).toBe('AI 助手暂时无法回答，请稍后重试。')
    expect(userFacingApiError('p3_disabled', 'market')).toBe('市场功能暂未开放；比赛和球员信息仍可正常使用。')
    expect(userFacingApiError('rate_limited', 'market')).toBe('请求过于频繁，请稍后再试。')
  })

  it('never repeats an unknown internal code in consumer-facing copy', () => {
    const message = userFacingApiError('unexpected_internal_state', 'match')

    expect(message).toBe('比赛详情暂时无法加载，请稍后重试。')
    expect(message).not.toContain('unexpected_internal_state')
  })
})
