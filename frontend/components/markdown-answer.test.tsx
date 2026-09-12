import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { MarkdownAnswer } from './markdown-answer'

describe('MarkdownAnswer', () => {
  it('renders common markdown and GFM structures as semantic elements', () => {
    render(
      <MarkdownAnswer
        content={[
          '# 比赛摘要',
          '',
          '> 事实来自冻结快照。',
          '',
          '| 球员 | ACE |',
          '| --- | ---: |',
          '| Sinner | **12** |',
          '| Ruud | 5 |',
          '',
          '- [x] 已核验',
          '- [ ] 暂未提供',
          '',
          '~~旧比分~~ **当前比分** `30–15`',
          '',
          '[查看详情](https://example.com/match)',
          '',
          '```text',
          'score: 6-4',
          '```',
        ].join('\n')}
      />,
    )

    expect(screen.getByRole('heading', { name: '比赛摘要' })).toBeVisible()
    expect(screen.getByRole('blockquote')).toHaveTextContent('事实来自冻结快照。')
    expect(screen.getByRole('table')).toBeVisible()
    expect(screen.getByTestId('markdown-table-scroll')).toBeVisible()
    expect(screen.getByRole('columnheader', { name: '球员' })).toBeVisible()
    expect(screen.getByRole('cell', { name: '12' })).toBeVisible()
    const checkboxes = screen.getAllByRole('checkbox')
    expect(checkboxes).toHaveLength(2)
    expect(checkboxes[0]).toBeChecked()
    expect(checkboxes[1]).not.toBeChecked()
    expect(screen.getByText('旧比分').tagName).toBe('DEL')
    expect(screen.getByText('当前比分').tagName).toBe('STRONG')
    expect(screen.getByText('30–15').tagName).toBe('CODE')
    expect(screen.getByRole('link', { name: '查看详情' })).toHaveAttribute(
      'href',
      'https://example.com/match',
    )
    expect(screen.getByText('score: 6-4').tagName).toBe('CODE')
  })

  it('renders the remaining GFM structures as semantic content', () => {
    render(
      <MarkdownAnswer
        content={[
          '#### 细节',
          '',
          '##### 证据',
          '',
          '###### 来源',
          '',
          '自动链接 https://example.com/match 和 email@example.com。',
          '',
          '数据来源[^source]',
          '',
          '[^source]: 官方比赛快照。',
        ].join('\n')}
      />,
    )

    expect(screen.getByRole('heading', { level: 4, name: '细节' })).toBeVisible()
    expect(screen.getByRole('heading', { level: 5, name: '证据' })).toBeVisible()
    expect(screen.getByRole('heading', { level: 6, name: '来源' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'https://example.com/match' })).toHaveAttribute(
      'href',
      'https://example.com/match',
    )
    expect(screen.getByRole('link', { name: 'email@example.com' })).toHaveAttribute(
      'href',
      'mailto:email@example.com',
    )
    expect(screen.getByText('官方比赛快照。')).toBeVisible()
  })
})
