import { describe, expect, it } from 'vitest'

import type { StructuredData } from '@/lib/api/types'
import { getChatAnswerLabel } from './chat-answer'

function withKind(kind: StructuredData['kind'], extra: Partial<StructuredData> = {}) {
  return { data: { kind, matches: [], ...extra } as StructuredData, error: null }
}

describe('getChatAnswerLabel', () => {
  it('keeps the existing labels for current-match results', () => {
    expect(getChatAnswerLabel(withKind('match'), 'global')).toBe('当前比赛')
    expect(getChatAnswerLabel(withKind('match'), 'match')).toBe('本场比赛结构化结果')
    expect(getChatAnswerLabel(withKind('matches'), 'global')).toBe('结构化比赛结果')
    expect(getChatAnswerLabel(withKind('matches'), 'match')).toBe('本场比赛结构化结果')
    expect(getChatAnswerLabel(withKind('intelligence'), 'match')).toBe('本场比赛分析')
    expect(getChatAnswerLabel(withKind('unsupported'), 'global')).toBe('暂不支持')
    expect(getChatAnswerLabel({ data: null, error: null }, 'global')).toBe('回答')
  })

  it('labels typed player history truthfully', () => {
    expect(getChatAnswerLabel(withKind('player_history'), 'global')).toBe('球员赛果与战绩')
    expect(getChatAnswerLabel(withKind('player_history'), 'match')).toBe('球员赛果与战绩')
  })

  it('labels P3 structured results by their domain', () => {
    const marketOpportunities = {
      data: { kind: 'market_opportunities', matches: [] } as unknown as StructuredData,
      error: null,
    }
    const matchDecision = {
      data: { kind: 'match_decision', matches: [] } as unknown as StructuredData,
      error: null,
    }

    expect(getChatAnswerLabel(marketOpportunities, 'global')).toBe('市场机会')
    expect(getChatAnswerLabel(matchDecision, 'match')).toBe('本场判断结果')
  })

  it('prioritizes the error label', () => {
    expect(
      getChatAnswerLabel(
        { data: null, error: { code: 'llm_unavailable' } },
        'global',
      ),
    ).toBe('查询未完成')
  })
})
