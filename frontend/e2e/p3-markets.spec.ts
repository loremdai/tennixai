import { expect, test, type Page } from '@playwright/test'

// T68 production /markets + Home pulse flows. The frontend proxy paths are
// intercepted with canonical backend payloads so the real Next routes,
// runtime decoders, hooks and components are exercised deterministically
// without a P3-enabled backend. The honest p3_disabled panel is verified
// against the real (P3-disabled) e2e backend.

const AS_OF = new Date().toISOString()

const DEFAULT_OPPORTUNITIES = {
  availability: { reason: 'HAS_OPPORTUNITIES', model_status: 'unknown' },
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

const DEFAULT_MARKETS = {
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
      model_availability: 'available',
      decision_action: 'buy',
      reason_code: null,
      player_ids: ['ply_a', 'ply_b'],
      player_names: ['E2E Alpha', 'E2E Beta'],
      model_probability: 0.62,
      quote: {
        state: 'snapshot',
        source: 'snapshot',
        as_of: AS_OF,
        outcome_bids: ['0.55', '0.43'],
        outcome_asks: ['0.57', '0.45'],
        best_bid: ['ply_a', '0.55'],
        best_ask: ['ply_a', '0.57'],
        spread: '0.0200',
        depth_usd: '306.00',
      },
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
      model_availability: 'out_of_scope',
      decision_action: null,
      reason_code: null,
      player_ids: null,
      player_names: null,
      model_probability: null,
      quote: {
        state: 'no_liquidity',
        source: 'snapshot',
        as_of: AS_OF,
        outcome_bids: null,
        outcome_asks: null,
        best_bid: null,
        best_ask: null,
        spread: null,
        depth_usd: null,
      },
      is_stale: false,
      has_gap: false,
      as_of: AS_OF,
    },
  ],
  page: 1,
  page_size: 50,
  total: 2,
}

/** Mutable payloads for per-test scenarios; reset before every test. */
let MARKETS: Record<string, unknown> = structuredClone(DEFAULT_MARKETS)
let OPPORTUNITIES: Record<string, unknown> = structuredClone(DEFAULT_OPPORTUNITIES)
let MARKET_PAGES: Record<number, Record<string, unknown>> = {}
let MARKET_REQUEST_PAGES: number[] = []

test.beforeEach(() => {
  MARKETS = structuredClone(DEFAULT_MARKETS)
  OPPORTUNITIES = structuredClone(DEFAULT_OPPORTUNITIES)
  MARKET_PAGES = {}
  MARKET_REQUEST_PAGES = []
})

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
  'event: ready\ndata: {"markets":2,"opportunities":2,"open_positions":1,"availability":"HAS_OPPORTUNITIES"}\n\n'

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
    const url = new URL(route.request().url())
    const path = url.pathname
    if (path === '/api/markets/stream') {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: SSE_READY,
      })
      return
    }
    let payload =
      path === '/api/markets/opportunities'
        ? OPPORTUNITIES
        : path === '/api/markets'
          ? MARKETS
          : path === '/api/paper/positions'
            ? PAPER
            : PULSE
    if (path === '/api/markets') {
      const pageNumber = Number(url.searchParams.get('page') ?? 1)
      MARKET_REQUEST_PAGES.push(pageNumber)
      payload = MARKET_PAGES[pageNumber] ?? MARKETS
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) })
  })
}

function defaultMarketRow(): Record<string, unknown> {
  return (DEFAULT_MARKETS.data as Array<Record<string, unknown>>)[0]
}

function marketRow(overrides: Record<string, unknown> = {}) {
  return {
    ...defaultMarketRow(),
    market_id: 'mkt_case',
    // A market without a decision observation has no action: it states its
    // quote state instead of an invented MARKET_ONLY badge.
    decision_action: null,
    ...overrides,
  }
}

function marketsPayload(rows: unknown[]) {
  return { data: rows, page: 1, page_size: 50, total: rows.length }
}

async function showAllMarkets(page: Page, rows: unknown[]) {
  MARKETS = marketsPayload(rows)
  await interceptP3(page)
  await page.goto('/markets?view=all')
  await page.getByRole('heading', { name: '市场决策支持' }).waitFor()
}

function minutesAgo(minutes: number): string {
  return new Date(Date.now() - minutes * 60_000).toISOString()
}

function quote(overrides: Record<string, unknown> = {}) {
  return {
    ...(defaultMarketRow().quote as Record<string, unknown>),
    as_of: minutesAgo(2),
    ...overrides,
  }
}

test.describe('P3 production market quote states (T88)', () => {
  test('loads later market pages and keeps filters local to loaded rows', async ({ page }) => {
    const firstPage = Array.from({ length: 50 }, (_, index) =>
      marketRow({
        market_id: `mkt_page_${index}`,
        tier: 'atp',
        gender: 'men',
        player_names: [`Player ${index}`, `Opponent ${index}`],
      }),
    )
    const tail = marketRow({
      market_id: 'mkt_page_tail',
      tier: 'wta',
      gender: 'women',
      player_names: ['Tail Player', 'Tail Opponent'],
    })
    MARKET_PAGES = {
      1: { data: firstPage, page: 1, page_size: 50, total: 51 },
      2: { data: [tail], page: 2, page_size: 50, total: 51 },
    }
    await interceptP3(page)
    await page.goto('/markets?view=all')

    await expect(page.getByText('已加载 50 / 51 场')).toBeVisible()
    await page.getByRole('button', { name: '女子' }).click()
    await expect(page.getByText('筛选后无市场')).toBeVisible()
    await page.getByRole('button', { name: '加载更多' }).click()
    await expect(page.getByRole('link', { name: '查看 Tail Player vs. Tail Opponent 市场' })).toBeVisible()
    await expect(page.getByText('已加载 51 / 51 场')).toBeVisible()
    expect(MARKET_REQUEST_PAGES.slice(-2)).toEqual([1, 2])
  })

  test('all markets show a real snapshot quote with its own time', async ({ page }) => {
    await showAllMarkets(page, [
      marketRow({
        market_id: 'mkt_snap',
        quote: quote({ state: 'snapshot', source: 'snapshot', as_of: minutesAgo(2) }),
      }),
    ])

    await expect(page.getByText(/快照报价 · 2 分前/)).toBeVisible()
    await expect(page.getByText('57.0%')).toBeVisible() // player one ask
    await expect(page.getByText('45.0%')).toBeVisible() // player two ask
  })

  test('partial, no-liquidity, stale and unavailable states stay distinct', async ({ page }) => {
    await showAllMarkets(page, [
      marketRow({
        market_id: 'mkt_partial',
        quote: quote({ state: 'partial', outcome_asks: ['0.60', null] }),
      }),
      marketRow({ market_id: 'mkt_empty', quote: quote({ state: 'no_liquidity' }) }),
      marketRow({ market_id: 'mkt_stale', quote: quote({ state: 'stale' }) }),
      marketRow({
        market_id: 'mkt_gone',
        quote: quote({ state: 'unavailable', source: null, as_of: null }),
      }),
    ])

    await expect(page.getByText(/部分报价 ·/)).toBeVisible()
    await expect(page.getByText('暂无挂单')).toBeVisible()
    await expect(page.getByText('最后可信报价已过期')).toBeVisible()
    await expect(page.getByText('报价暂不可用')).toBeVisible()
    // The one-sided quote keeps its real ask instead of hiding both.
    await expect(page.getByText('60.0%')).toBeVisible()
  })

  test('low-tier markets keep real quotes and no negative model label', async ({ page }) => {
    await showAllMarkets(page, [
      marketRow({
        market_id: 'mkt_challenger',
        tier: 'challenger',
        model_availability: 'out_of_scope',
        decision_action: null,
        quote: quote({ state: 'snapshot', source: 'snapshot', as_of: minutesAgo(1) }),
      }),
    ])

    // The tier chip also carries this text, so scope the badge to the row.
    await expect(
      page.getByRole('link', { name: '查看 E2E Alpha vs. E2E Beta 市场' }).getByText('Challenger'),
    ).toBeVisible()
    await expect(page.getByText('快照报价 · 1 分前')).toBeVisible()
    await expect(page.getByText(/未覆盖|不伪造模型值/)).toHaveCount(0)
  })

  test('row navigation follows the active link only', async ({ page }) => {
    await showAllMarkets(page, [
      marketRow({ market_id: 'mkt_linked', match_id: 'mat_e2e_1' }),
      marketRow({
        market_id: 'mkt_free',
        match_id: null,
        question: 'E2E Unlinked Moneyline',
        tier: 'itf',
        decision_action: null,
        model_availability: 'out_of_scope',
      }),
    ])

    await expect(
      page.getByRole('link', { name: /查看 E2E Alpha vs\. E2E Beta 市场/ }),
    ).toHaveAttribute('href', '/matches/mat_e2e_1')
    await expect(page.getByText('E2E Unlinked Moneyline')).toBeVisible()
    await expect(
      page.getByRole('link', { name: /E2E Unlinked Moneyline 市场/ }),
    ).toHaveCount(0)
  })

  test('the opportunities tab explains an unpromoted model', async ({ page }) => {
    OPPORTUNITIES = {
      data: [],
      availability: { reason: 'ELIGIBLE_UNPROMOTED', model_status: 'not_promoted' },
    }
    await interceptP3(page)
    await page.goto('/markets?view=opportunities')

    await expect(
      page.getByRole('heading', { name: '模型尚未完成验证' }),
    ).toBeVisible()
    await expect(
      page.getByText('模型尚未完成验证，当前不生成 BUY / WAIT；全部市场的真实报价仍可查看。'),
    ).toBeVisible()
    await expect(page.getByText('BUY', { exact: true })).toHaveCount(0)
    await expect(page.getByText('WAIT', { exact: true })).toHaveCount(0)
  })

  test('a real actionable opportunity still renders as BUY', async ({ page }) => {
    await interceptP3(page)
    await page.goto('/markets?view=opportunities')

    await expect(
      page.getByRole('link', { name: /查看 E2E Alpha vs\. E2E Beta 的 buy 决策/ }),
    ).toBeVisible()
  })
})

test.describe('P3 production mobile', () => {
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
    // The low-tier row states its real quote state instead of a model label.
    await expect(page.getByText('暂无挂单')).toBeVisible()

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

  test('quote labels and the unpromoted empty state stay legible', async ({ page }) => {
    await showAllMarkets(page, [
      marketRow({
        market_id: 'mkt_snap',
        quote: quote({ state: 'snapshot', source: 'snapshot', as_of: minutesAgo(2) }),
      }),
    ])
    await expect(page.getByText(/快照报价 · 2 分前/)).toBeVisible()

    OPPORTUNITIES = {
      data: [],
      availability: { reason: 'ELIGIBLE_UNPROMOTED', model_status: 'not_promoted' },
    }
    await page.goto('/markets?view=opportunities')
    await expect(
      page.getByRole('heading', { name: '模型尚未完成验证' }),
    ).toBeVisible()

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    )
    expect(overflow).toBeLessThanOrEqual(0)
  })

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
