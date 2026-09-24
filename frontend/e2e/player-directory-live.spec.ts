import { expect, test, type Page } from '@playwright/test'

/**
 * Bounded live gate for the production player pages against the real
 * API-Tennis directory (webServer runs with TENNIX_PROVIDER_MODE=api_tennis
 * when TENNIX_E2E_API_TENNIS=1 and a key exists in the root .env).
 * Chat journey items additionally require TENNIX_E2E_REAL_LLM=1.
 * Skipped honestly in every other environment; never updates snapshots.
 */

test.skip(
  process.env.TENNIX_E2E_API_TENNIS !== '1',
  'player-directory-live requires TENNIX_E2E_API_TENNIS=1',
)

const FORBIDDEN_PAYLOAD = /player_key|first_player_key|second_player_key|event_key|api_key|Bearer\s/i

function watchPage(page: Page) {
  const consoleErrors: string[] = []
  const payloadHits: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('response', async (response) => {
    if (!response.url().includes('/api/players')) return
    const body = await response.text().catch(() => '')
    if (FORBIDDEN_PAYLOAD.test(body)) payloadHits.push(response.url())
  })
  return { consoleErrors, payloadHits }
}

async function waitForChatCompletion(page: Page) {
  const assistant = page.locator('#assistant')
  const answer = assistant.getByTestId('markdown-answer')
  await expect(answer).toBeVisible({ timeout: 120_000 })
  await expect(answer).toHaveText(/\S+/, { timeout: 30_000 })
  await expect(assistant).not.toContainText('查询失败', { timeout: 5_000 })
}

test('live directory - official rankings, WTA switch and China filter', async ({ page }) => {
  const { consoleErrors, payloadHits } = watchPage(page)

  await page.goto('/players')
  await expect(page.getByRole('heading', { name: 'ATP 单打世界排名' })).toBeVisible({ timeout: 60_000 })
  const atpRows = page.getByRole('region', { name: 'ATP 世界排名列表' }).getByRole('listitem')
  await expect(atpRows.first()).toBeVisible({ timeout: 60_000 })
  expect(await atpRows.count()).toBe(50)
  await expect(page.getByText(/共 \d+ 位/)).toBeVisible()

  await page.getByRole('tab', { name: 'WTA' }).click()
  await expect(page.getByRole('heading', { name: 'WTA 单打世界排名' })).toBeVisible({ timeout: 60_000 })
  const wtaRows = page.getByRole('region', { name: 'WTA 世界排名列表' }).getByRole('listitem')
  await expect(wtaRows.first()).toBeVisible({ timeout: 60_000 })

  await page.getByRole('button', { name: '仅看中国球员' }).click()
  const chnRows = page.getByRole('region', { name: 'WTA 世界排名列表' }).getByRole('listitem')
  await expect(chnRows.first()).toBeVisible({ timeout: 60_000 })
  const total = await chnRows.count()
  expect(await chnRows.filter({ hasText: 'CHN' }).count()).toBe(total)

  expect(payloadHits).toEqual([])
  expect(consoleErrors.filter((text) => !text.includes('React DevTools'))).toEqual([])
})

test('live directory - Chinese search resolves Ben Shelton and opens the profile', async ({ page }) => {
  const { payloadHits } = watchPage(page)

  await page.goto('/players')
  await expect(page.getByRole('heading', { name: 'ATP 单打世界排名' })).toBeVisible({ timeout: 60_000 })
  await page.locator('#player-directory-search').fill('谢尔顿')
  await page.locator('#player-directory-search').press('Enter')

  const shelton = page.getByRole('link', { name: /Ben Shelton/ }).first()
  await expect(shelton).toBeVisible({ timeout: 60_000 })
  await shelton.click()

  await expect(page.getByRole('heading', { level: 1, name: 'Ben Shelton' })).toBeVisible({ timeout: 60_000 })
  await expect(page.getByRole('heading', { name: '赛季摘要' })).toBeVisible({ timeout: 60_000 })
  await expect(page.getByRole('heading', { name: '当前比赛状态' })).toBeVisible()

  expect(payloadHits).toEqual([])
})

test('live directory - season filters, pagination and finished match navigation', async ({ page }) => {
  const { payloadHits } = watchPage(page)

  await page.goto('/players')
  await expect(page.getByRole('heading', { name: 'ATP 单打世界排名' })).toBeVisible({ timeout: 60_000 })
  await page.locator('#player-directory-search').fill('Ben Shelton')
  await page.locator('#player-directory-search').press('Enter')
  await page.getByRole('link', { name: /Ben Shelton/ }).first().click()
  await expect(page.getByRole('heading', { level: 1, name: 'Ben Shelton' })).toBeVisible({ timeout: 60_000 })

  const results = page.getByRole('region', { name: 'Ben Shelton 历史赛果列表' })
  await expect(results).toBeVisible({ timeout: 60_000 })
  const footer = page.getByText(/1–20 \/ 共 \d+ 场/)
  await expect(footer).toBeVisible({ timeout: 60_000 })

  const next = page.getByRole('button', { name: '下一页' }).last()
  if (await next.isEnabled()) {
    await next.click()
    await expect(page.getByText(/21–\d+ \/ 共 \d+ 场/)).toBeVisible({ timeout: 60_000 })
    await page.getByRole('button', { name: '上一页' }).last().click()
  }

  await page.getByRole('button', { name: '赛果：全部结果' }).click()
  await page.getByRole('menuitem', { name: '胜' }).click()
  await expect(results.getByText('负', { exact: true })).toHaveCount(0, { timeout: 60_000 })

  await results.getByRole('link').first().click()
  await page.waitForURL(/\/matches\/[^/]+$/, { timeout: 60_000 })

  expect(payloadHits).toEqual([])
})

test.describe('live directory - Home/Match chat journey', () => {
  test.skip(
    process.env.TENNIX_E2E_REAL_LLM !== '1',
    'chat journey items require TENNIX_E2E_REAL_LLM=1',
  )

  type HistoryEntry = {
    player: { id: string; name: string; localized_name: string | null }
    scope: 'yesterday' | 'last' | 'recent' | 'season'
    season: number | null
    season_record: { matches_won: number; matches_lost: number; titles: number } | null
    empty_reason: string | null
    matches: Array<{ id: string; status: string }>
  }

  const SCOPE_LABELS: Record<HistoryEntry['scope'], string> = {
    yesterday: '昨日赛果',
    last: '上一场比赛',
    recent: '近期赛果',
    season: '赛季战绩',
  }

  function parseHistoryEntries(body: string): HistoryEntry[] {
    const entries: HistoryEntry[] = []
    for (const line of body.split('\n')) {
      if (!line.startsWith('data: ')) continue
      try {
        const payload = JSON.parse(line.slice('data: '.length))
        if (payload?.kind === 'player_history' && payload.player_history) {
          entries.push({ ...(payload.player_history as HistoryEntry), matches: payload.matches ?? [] })
        }
      } catch {
        // Non-JSON or partial frame: keep scanning.
      }
    }
    return entries
  }

  async function askHistoryQuestion(page: Page, question: string): Promise<string> {
    const bodies: string[] = []
    page.on('response', (response) => {
      if (!response.url().includes('chat/stream')) return
      void response
        .text()
        .then((text) => bodies.push(text))
        .catch(() => {})
    })
    await page.goto('/')
    await page.getByLabel('向 Tennix 提问').fill(question)
    await page.getByLabel('向 Tennix 提问').press('Enter')
    await waitForChatCompletion(page)
    await expect
      .poll(() => bodies.some((body) => body.includes('event: done')), { timeout: 30_000 })
      .toBe(true)
    return bodies.join('\n')
  }

  async function assertHistorySections(page: Page, body: string) {
    const entries = parseHistoryEntries(body)
    expect(entries.length).toBeGreaterThan(0)
    // SSE completed without a terminal error frame.
    expect(body).toContain('event: done')
    expect(body).not.toContain('event: error')
    expect(FORBIDDEN_PAYLOAD.test(body)).toBe(false)

    const assistant = page.locator('#assistant')
    const sections = assistant.getByTestId('player-history-section')
    await expect(sections).toHaveCount(entries.length, { timeout: 30_000 })

    // Query-level title follows the approved rules.
    if (entries.length === 1) {
      const entry = entries[0]
      const heading = entry.player.localized_name
        ? `${entry.player.name}（${entry.player.localized_name}）`
        : entry.player.name
      await expect(
        assistant.getByRole('heading', {
          name: entry.scope === 'season' ? `${heading} · ${entry.season} 赛季战绩` : `${heading} · ${SCOPE_LABELS[entry.scope]}`,
        }),
      ).toBeVisible()
    } else {
      await expect(assistant.getByRole('heading', { name: '球员赛果与战绩' })).toBeVisible()
    }

    for (let index = 0; index < entries.length; index += 1) {
      const entry = entries[index]
      const section = sections.nth(index)
      await expect(section.getByRole('heading', { name: entry.player.name })).toBeVisible()
      if (entry.scope === 'season') {
        if (entry.season_record) {
          const summary = section.getByTestId('season-record-summary')
          await expect(summary).toBeVisible()
          await expect(summary).toContainText(String(entry.season_record.matches_won))
        } else {
          await expect(section.getByText('该赛季战绩暂不可用')).toBeVisible()
        }
      } else if (entry.matches.length > 0) {
        // All returned matches are finished and link to internal match pages.
        expect(entry.matches.every((match) => match.status === 'finished')).toBe(true)
        const firstLink = section.getByRole('link', { name: /打开比赛：/ }).first()
        await expect(firstLink).toBeVisible()
        expect(await firstLink.getAttribute('href')).toBe(`/matches/${entry.matches[0].id}`)
        await expect(section.getByText('已完赛').first()).toBeVisible()
      } else {
        await expect(section.getByText('该范围暂无赛果信息')).toBeVisible()
      }
    }
    // History answers never reuse the generic current-match empty title.
    await expect(assistant.getByText('没有符合条件的比赛')).toHaveCount(0)
  }

  const historyQuestions = [
    '辛纳上一次比赛是什么时候？',
    '郑钦文最近赛果如何？',
    '辛纳上一次比赛是什么时候？郑钦文赛果如何？',
    '郑钦文这个赛季战绩如何？',
    'Shelton last match',
  ]

  for (const question of historyQuestions) {
    test(`home history content: ${question}`, async ({ page }) => {
      const { consoleErrors, payloadHits } = watchPage(page)
      const body = await askHistoryQuestion(page, question)
      await assertHistorySections(page, body)
      expect(payloadHits).toEqual([])
      expect(consoleErrors.filter((text) => !text.includes('React DevTools'))).toEqual([])
    })
  }

  test('ambiguous or unknown surname ends with candidates or clarification and done', async ({ page }) => {
    await page.goto('/')
    await page.getByLabel('向 Tennix 提问').fill('Wang 最近战绩如何？')
    await page.getByLabel('向 Tennix 提问').press('Enter')
    await waitForChatCompletion(page)
    // Both recoverable resolver outcomes are acceptable: an ambiguous
    // candidate list or an honest clarification asking for more detail.
    const assistant = page.locator('#assistant')
    await expect(
      assistant
        .getByText('多位候选球员，请选择')
        .or(assistant.getByText(/请补充|未能找到|未找到|没有关于/))
        .first(),
    ).toBeVisible({ timeout: 5_000 })
  })

  test('match chat answers Shelton serve questions in match context', async ({ page }) => {
    await page.goto('/')
    await page.getByLabel('向 Tennix 提问').fill('谢尔顿现在比分多少？')
    await page.getByLabel('向 Tennix 提问').press('Enter')
    await waitForChatCompletion(page)

    const card = page.getByRole('link', { name: /打开比赛：/ }).first()
    if (!(await card.isVisible().catch(() => false))) {
      test.info().annotations.push({
        type: 'note',
        description: 'no Shelton match card currently offered; match chat covered by deterministic gates',
      })
      return
    }
    await card.click()
    await page.getByLabel('继续就这场比赛提问').fill('Shelton 现在在发球吗？')
    await page.getByLabel('继续就这场比赛提问').press('Enter')
    await waitForChatCompletion(page)
  })
})
