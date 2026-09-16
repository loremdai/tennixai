import { expect, test, type Page } from '@playwright/test'

// T68 production /markets + Home pulse flows. The frontend proxy paths are
// intercepted with canonical backend payloads so the real Next routes,
// runtime decoders, hooks and components are exercised deterministically
// without a P3-enabled backend. The honest p3_disabled panel is verified
// against the real (P3-disabled) e2e backend.

const AS_OF = new Date().toISOString()

const OPPORTUNITIES = {
  data: [
    {
      match_id: 'mat_e2e_1',
      market_id: 'mkt_e2e_1',
      phase: 'live',
      action: 'buy',
      target_player_id: 'ply_a',
      player_ids: ['ply_a', 'ply_b'],
      player_names: ['E2E Alpha', 'E2E Beta'],
      model_probability: 0.62,
      executable_probability: 0.55,
      conservative_net_edge: '0.0700',
      max_acceptable_price: null,
      tournament_tier: 'atp',
      tournament_name: 'E2E Open',
      is_stale: false,
      has_gap: false,
      as_of: AS_OF,
    },
    {
      match_id: 'mat_e2e_2',
      market_id: 'mkt_e2e_2',
      phase: 'upcoming',
      action: 'wait',
      target_player_id: 'ply_c',
      player_ids: ['ply_c', 'ply_d'],
      player_names: ['E2E Gamma', 'E2E Delta'],
      model_probability: 0.58,
      executable_probability: 0.57,
      conservative_net_edge: null,
      max_acceptable_price: '0.5500',
      tournament_tier: 'wta',
      tournament_name: 'E2E Trophy',
      is_stale: false,
      has_gap: false,
      as_of: AS_OF,
    },
  ],
}

const MARKETS = {
  data: [
    {
      market_id: 'mkt_e2e_1',
      match_id: 'mat_e2e_1',
      question: null,
      status: 'open',
      tournament_name: 'E2E Open',
      tier: 'atp',
      gender: 'men',
      phase: 'live',
      model_covered: true,
      action: 'buy',
      reason_code: null,
      player_ids: ['ply_a', 'ply_b'],
      player_names: ['E2E Alpha', 'E2E Beta'],
      model_probability: 0.62,
      best_bid: ['ply_a', '0.55'],
      best_ask: ['ply_a', '0.57'],
      outcome_bids: ['0.55', '0.43'],
      outcome_asks: ['0.57', '0.45'],
      spread: '0.0200',
      depth_usd: '306.00',
      is_stale: false,
      has_gap: false,
      as_of: AS_OF,
    },
    {
      market_id: 'mkt_e2e_c',
      match_id: null,
      question: 'E2E Challenger Moneyline',
      status: 'open',
      tournament_name: 'E2E Challenger',
      tier: 'challenger',
      gender: 'men',
      phase: 'prematch',
      model_covered: false,
      action: 'market_only',
      reason_code: null,
      player_ids: null,
      player_names: null,
      model_probability: null,
      best_bid: null,
      best_ask: null,
      outcome_bids: null,
      outcome_asks: null,
      spread: null,
      depth_usd: null,
      is_stale: false,
      has_gap: false,
      as_of: AS_OF,
    },
  ],
  page: 1,
  page_size: 50,
  total: 2,
}

const PAPER = {
  open: [
    {
      position_id: 'pos_e2e_1',
      match_id: 'mat_e2e_1',
      market_id: 'mkt_e2e_1',
      tournament_name: 'E2E Open',
      outcome_player_id: 'ply_a',
      player_ids: ['ply_a', 'ply_b'],
      player_names: ['E2E Alpha', 'E2E Beta'],
      status: 'open',
      entry_cost: '10.00',
      shares: '19.05',
      average_entry_price: '0.525',
      current_exit_value: '11.40',
      net_pnl: null,
      freshness_as_of: AS_OF,
    },
  ],
  recent: [
    {
      position_id: 'pos_e2e_0',
      match_id: 'mat_e2e_0',
      market_id: 'mkt_e2e_0',
      tournament_name: 'E2E Open',
      outcome_player_id: 'ply_b',
      player_ids: ['ply_a', 'ply_b'],
      player_names: ['E2E Alpha', 'E2E Beta'],
      status: 'settled',
      entry_cost: '10.00',
      shares: '19.05',
      average_entry_price: '0.525',
      current_exit_value: null,
      net_pnl: '1.40',
      freshness_as_of: AS_OF,
    },
  ],
}

const PULSE = {
  data: [
    {
      match_id: 'mat_e2e_1',
      market_id: 'mkt_e2e_1',
      kind: 'position',
      action: 'hold',
      phase: 'live',
      player_names: ['E2E Alpha', 'E2E Beta'],
      model_probability: 0.62,
      executable_probability: 0.57,
      conservative_net_edge: '0.0300',
      tournament_name: 'E2E Open',
      is_stale: false,
      has_gap: false,
      as_of: AS_OF,
    },
    {
      match_id: 'mat_e2e_2',
      market_id: 'mkt_e2e_2',
      kind: 'opportunity',
      action: 'buy',
      phase: 'live',
      player_names: ['E2E Gamma', 'E2E Delta'],
      model_probability: 0.6,
      executable_probability: 0.55,
      conservative_net_edge: '0.0500',
      tournament_name: 'E2E Trophy',
      is_stale: false,
      has_gap: false,
      as_of: AS_OF,
    },
  ],
  has_open_position: true,
}

const SSE_READY =
  'event: ready\ndata: {"markets":2,"opportunities":2,"open_positions":1}\n\n'

async function interceptP3(page: Page) {
  await page.route((url) => {
    const path = url.pathname
    return (
      path === '/api/markets' ||
      path === '/api/markets/opportunities' ||
      path === '/api/markets/pulse' ||
      path === '/api/markets/stream' ||
      path === '/api/paper/positions'
    )
  }, async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/markets/stream') {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: SSE_READY,
      })
      return
    }
    const payload =
      path === '/api/markets/opportunities'
        ? OPPORTUNITIES
        : path === '/api/markets'
          ? MARKETS
          : path === '/api/paper/positions'
            ? PAPER
            : PULSE
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) })
  })
}

test.describe('P3 production markets flows', () => {
  test('direct /markets load renders canonical opportunity rows', async ({ page }) => {
    await interceptP3(page)
    await page.goto('/markets')

    await expect(page.getByRole('heading', { name: '市场决策支持' })).toBeVisible()
    await expect(page.getByText('E2E Alpha vs. E2E Beta')).toBeVisible()
    await expect(page.getByText('方向：E2E Alpha')).toBeVisible()
    await expect(page.getByText('+7.0pp')).toBeVisible()
    await expect(page.getByRole('link', { name: /查看 E2E Alpha vs\. E2E Beta 的 buy 决策/ })).toHaveAttribute(
      'href',
      '/matches/mat_e2e_1',
    )
  })

  test('each tab renders its canonical view', async ({ page }) => {
    await interceptP3(page)
    await page.goto('/markets')

    await page.getByRole('tab', { name: /全部市场/ }).click()
    await expect(page.getByText('市场筛选')).toBeVisible()
    await expect(page.getByText('E2E Challenger Moneyline')).toBeVisible()
    await expect(page.getByText('仅市场数据')).toBeVisible()

    await page.getByRole('tab', { name: /^Paper/ }).click()
    await expect(page.getByText('Paper 生命周期账本')).toBeVisible()
    await expect(page.getByText('2 条')).toBeVisible()
    await expect(page.getByText('+$1.40')).toBeVisible()
  })

  test('canonical filters narrow rows and sync the URL', async ({ page }) => {
    await interceptP3(page)
    await page.goto('/markets')
    await page.getByRole('tab', { name: /全部市场/ }).click()
    await expect(page.getByText('E2E Challenger Moneyline')).toBeVisible()

    await page.getByRole('button', { name: 'Challenger', exact: true }).click()
    await expect(page.getByText('E2E Challenger Moneyline')).toBeVisible()
    // The ATP row is filtered out of the list.
    await expect(page.locator('h3', { hasText: 'E2E Alpha vs. E2E Beta' })).toHaveCount(0)
    expect(page.url()).toContain('tier=challenger')

    await page.getByRole('button', { name: '重置' }).click()
    await expect(page.locator('h3', { hasText: 'E2E Alpha vs. E2E Beta' })).toHaveCount(1)
    expect(page.url()).not.toContain('tier=challenger')
  })

  test('Home pulse → Markets → Match navigation', async ({ page }) => {
    await interceptP3(page)
    // ?p3=1 force-mounts the live pulse (the shared e2e backend runs with
    // P3 disabled, and the server-side probe cannot be intercepted).
    await page.goto('/?p3=1')

    await expect(page.getByRole('heading', { name: '市场脉搏' })).toBeVisible()
    await expect(page.getByRole('link', { name: /查看全部/ })).toHaveAttribute('href', '/markets')

    await page.getByRole('link', { name: /查看全部/ }).click()
    await page.waitForURL('/markets')
    await expect(page.getByText('E2E Alpha vs. E2E Beta')).toBeVisible()

    await page
      .getByRole('link', { name: /查看 E2E Alpha vs\. E2E Beta 的 buy 决策/ })
      .click()
    await page.waitForURL('/matches/mat_e2e_1')
  })

  test('refresh keeps the workspace functional', async ({ page }) => {
    await interceptP3(page)
    await page.goto('/markets')
    await expect(page.getByText('E2E Alpha vs. E2E Beta')).toBeVisible()

    await page.reload()
    await expect(page.getByText('E2E Alpha vs. E2E Beta')).toBeVisible()
    await expect(page.getByRole('heading', { name: '市场决策支持' })).toBeVisible()
  })

  test('keyboard users can traverse tabs and rows', async ({ page }) => {
    await interceptP3(page)
    await page.goto('/markets')
    await expect(page.getByText('E2E Alpha vs. E2E Beta')).toBeVisible()

    await page.getByRole('tab', { name: /机会/ }).focus()
    await page.keyboard.press('ArrowRight')
    await expect(page.getByRole('tab', { name: /全部市场/ })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    await expect(page.getByText('市场筛选')).toBeVisible()
  })
})

test.describe('P3 production mobile', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('no horizontal overflow and 44px touch targets', async ({ page }) => {
    await interceptP3(page)
    await page.goto('/markets')
    await expect(page.getByText('E2E Alpha vs. E2E Beta')).toBeVisible()

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    )
    expect(overflow).toBeLessThanOrEqual(0)

    await page.getByRole('tab', { name: /全部市场/ }).click()
    const chip = page.getByRole('button', { name: 'Challenger', exact: true })
    const box = await chip.boundingBox()
    expect(box).not.toBeNull()
    expect(box!.height).toBeGreaterThanOrEqual(44)

    const tabBox = await page.getByRole('tab', { name: /全部市场/ }).boundingBox()
    expect(tabBox!.height).toBeGreaterThanOrEqual(44)
  })
})

test.describe('P3 disabled backend', () => {
  test('the production workspace shows the honest disabled panel', async ({ page }) => {
    // No interception: the real e2e backend runs with P3 disabled and the
    // proxy passes the typed 503 through.
    await page.goto('/markets')
    await expect(page.getByText('市场决策支持未启用')).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText(/p3_disabled/)).toBeVisible()
  })
})
