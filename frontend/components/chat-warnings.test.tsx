import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ChatWarnings } from './chat-warnings'

describe('ChatWarnings', () => {
  it('labels LLM safety corrections as answer quality feedback', () => {
    render(
      <ChatWarnings
        warnings={[
          {
            code: 'llm_response_repaired',
            message: 'AI 回答已重新校验。',
            details: {},
          },
        ]}
      />,
    )

    expect(screen.getByText('回答质量提示')).toBeVisible()
  })

  it('keeps data availability warnings clearly labeled', () => {
    render(
      <ChatWarnings
        warnings={[
          {
            code: 'optional_data_unavailable',
            message: '部分资料暂未提供。',
            details: {},
          },
        ]}
      />,
    )

    expect(screen.getByText('部分资料暂未提供')).toBeVisible()
  })
})
