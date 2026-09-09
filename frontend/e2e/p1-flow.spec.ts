import { expect, test } from '@playwright/test'

test.describe('P1 flow', () => {
  test('home question renders a structured card that opens the internal match page', async ({ page }) => {
    await page.goto('/')
    await page.getByLabel('继续向 Tennix 提问').fill('Sinner 今晚几点比赛？')
    await page.getByLabel('继续向 Tennix 提问').press('Enter')

    const card = page.getByRole('link', { name: /打开比赛：Sinner 对阵/ }).first()
    await expect(card).toBeVisible()
    const href = await card.getAttribute('href')
    expect(href).toMatch(/^\/matches\/mat_/)

    await card.click()
    await expect(page.getByRole('heading', { name: /Sinner/ }).first()).toBeVisible()
    await expect(page.getByText('P2 数据暂不可用').first()).toBeVisible()
  })

  test('keeps structured cards in the viewport after a long markdown answer', async ({ page }) => {
    const match = {
      id: 'mat_e2e_upcoming',
      status: 'scheduled',
      players: [
        { id: 'ply_e2e_sinner', name: 'Jannik Sinner', country_code: 'ita', ranking: 1 },
        { id: 'ply_e2e_alcaraz', name: 'Carlos Alcaraz', country_code: 'esp', ranking: 2 },
      ],
      tournament: { id: 'trn_e2e', name: 'ATP Finals', tour: 'atp' },
      scheduled_at: '2026-09-08T12:30:00Z',
      round: 'Semifinal',
      surface: 'hard',
      indoor: true,
      format: 'BO3',
      live_state: null,
      winner_player_id: null,
      freshness: {
        provider: 'fake',
        source_updated_at: null,
        observed_at: '2026-09-08T10:00:00Z',
        is_stale: false,
        age_seconds: 0,
      },
    }
    const events = [
      'event: status\ndata: {"stage":"resolving"}',
      `event: data\ndata: ${JSON.stringify({ kind: 'matches', matches: [match] })}`,
      `event: text_delta\ndata: ${JSON.stringify({
        delta: [
          '当前查到 **Sinner** 的比赛。',
          '',
          '- **对手**：Carlos Alcaraz',
          '- **赛事**：ATP Finals',
          '- **轮次**：Semifinal',
          '- **场地**：硬地',
          '- **赛制**：BO3',
        ].join('\n'),
      })}`,
      'event: done\ndata: {"ok":true}',
      '',
    ].join('\n\n')

    await page.route('**/api/chat/stream', (route) =>
      route.fulfill({
        status: 200,
        headers: { 'content-type': 'text/event-stream' },
        body: events,
      }),
    )

    await page.goto('/')
    await page.getByLabel('继续向 Tennix 提问').fill('Sinner 下一场比赛是什么时候？')
    await page.getByLabel('继续向 Tennix 提问').press('Enter')

    const card = page.getByRole('link', { name: '打开比赛：Sinner 对阵 Alcaraz' })
    await expect(card).toBeVisible()
    await expect(card).toBeInViewport()
  })

  test('match page answers a contextual question without repeating the match', async ({ page }) => {
    await page.goto('/')
    const featured = page.getByRole('link', { name: '打开比赛', exact: true })
    await expect(featured).toBeVisible()
    await featured.click()

    await page.getByLabel('向 Tennix 询问本场比赛').fill('谁在发球？')
    await page.getByLabel('向 Tennix 询问本场比赛').press('Enter')

    await expect(page.getByText('已获取本场比赛的结构化数据。')).toBeVisible()
    const serverIndicator = page.locator('#server-indicator')
    await expect(serverIndicator).toBeVisible()
  })

  test('explicit refresh reloads match data', async ({ page }) => {
    await page.goto('/')
    const featured = page.getByRole('link', { name: '打开比赛', exact: true })
    await expect(featured).toBeVisible()

    const requests: string[] = []
    page.on('request', (request) => {
      if (/\/api\/matches\/mat_/.test(request.url())) requests.push(request.url())
    })
    await featured.click()
    await expect(page.locator('#match')).toBeVisible()

    const refresh = page.getByRole('button', { name: '刷新比赛数据' })
    await expect(refresh).toBeVisible()
    await refresh.click()
    await expect(page.locator('#match')).toBeVisible()
    expect(requests.length).toBeGreaterThanOrEqual(2)
  })

  test('historical question returns typed unsupported without a card', async ({ page }) => {
    await page.goto('/')
    await page.getByLabel('继续向 Tennix 提问').fill('昨天 Sinner 赢了吗？')
    await page.getByLabel('继续向 Tennix 提问').press('Enter')

    await expect(page.getByText('P1 暂不支持历史比赛结果查询。')).toBeVisible()
    await expect(page.getByRole('link', { name: /打开比赛：/ }).first()).toBeHidden()
  })

  test('provider failure renders typed retry copy on home', async ({ page }) => {
    await page.route('**/api/matches*', (route) => {
      if (route.request().url().includes('/api/matches?')) {
        return route.fulfill({
          status: 503,
          contentType: 'application/json',
          body: JSON.stringify({
            error: { code: 'provider_unavailable', message: 'LiveTennisAPI request failed', details: {} },
            request_id: 'req-test',
          }),
        })
      }
      return route.continue()
    })

    await page.goto('/')
    await expect(page.getByText(/比赛数据加载失败（provider_unavailable）/)).toBeVisible()
    await expect(page.getByRole('button', { name: '重试加载比赛数据' })).toBeVisible()
  })
})
