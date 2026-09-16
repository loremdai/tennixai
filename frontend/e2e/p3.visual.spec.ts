import { test, type Page } from '@playwright/test'

const homeCases = [
  ['populated', 'home-populated'],
  ['stale', 'home-stale'],
  ['empty', 'home-empty'],
  ['populated', 'home-query-preserved'],
] as const

const marketCases = [
  ['view=opportunities&state=populated', 'markets-opportunities'],
  ['view=opportunities&state=empty', 'markets-empty'],
  ['view=opportunities&state=partial_stale', 'markets-partial-stale'],
  ['view=all&state=populated', 'markets-all'],
  ['view=all&state=filtered_empty&tier=itf&gender=women', 'markets-filter-empty'],
  ['view=all&state=supplier_empty', 'markets-supplier-empty'],
  ['view=paper&state=open', 'markets-paper-open'],
  ['view=paper&state=terminal', 'markets-paper-terminal'],
] as const

const matchCases = [
  ['market_only', 'match-market-only'],
  ['no_bet', 'match-no-bet'],
  ['wait', 'match-wait'],
  ['buy', 'match-buy'],
  ['entry_pending', 'match-entry-pending'],
  ['missed', 'match-missed'],
  ['hold', 'match-hold'],
  ['sell', 'match-sell'],
  ['exit_pending', 'match-exit-pending'],
  ['exited', 'match-exited'],
  ['exit_missed', 'match-exit-missed'],
  ['settled', 'match-settled'],
  ['buy&overlay=stale', 'match-stale'],
  ['buy&overlay=gap', 'match-gap'],
] as const

async function capture(page: Page, url: string, name: string, mobile: boolean) {
  await page.setViewportSize(mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 })
  await page.goto(url)
  await page.getByRole('main').waitFor()
  await page.screenshot({ path: `/tmp/agent-browser/p3-candidates/${name}-${mobile ? 'mobile' : 'desktop'}.png`, fullPage: true })
}

test.describe('P3 preview candidate baselines', () => {
  test('Home 4 candidate baselines', async ({ page, baseURL }) => {
    for (const [query, name] of homeCases) {
      await capture(page, `${baseURL}/?preview=p3&pulse=${query}`, name, false)
      await capture(page, `${baseURL}/?preview=p3&pulse=${query}`, name, true)
    }
  })

  test('Markets 8 candidate baselines', async ({ page, baseURL }) => {
    for (const [query, name] of marketCases) {
      await capture(page, `${baseURL}/markets?preview=p3&${query}`, name, false)
      await capture(page, `${baseURL}/markets?preview=p3&${query}`, name, true)
    }
  })

  test('Match 14 candidate baselines', async ({ page, baseURL }) => {
    for (const [query, name] of matchCases) {
      await capture(page, `${baseURL}/match?preview=p3&state=${query}`, name, false)
      await capture(page, `${baseURL}/match?preview=p3&state=${query}`, name, true)
    }
  })
})
