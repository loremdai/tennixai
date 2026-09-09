import { expect, test } from '@playwright/test'

import type { FacetCountsDto, MatchCatalogDto, MatchDto } from '../lib/api/types'

const FACET_ONE_COUNTS: FacetCountsDto = {
  circuits: { atp: 1, wta: 1, challenger: 1, itf: 1, other: 1 },
  genders: { men: 1, women: 1, mixed: 1, unknown: 1 },
  disciplines: { singles: 1, doubles: 1, team: 1, unknown: 1 },
}

const ITF_WOMEN_DOUBLES: MatchDto = {
  id: 'mat_itf_women_doubles',
  status: 'scheduled',
  players: [
    { id: 'ply_itf_a', name: 'Hontama/ Kubka', country_code: null, ranking: null },
    { id: 'ply_itf_b', name: 'Liu/ Sun', country_code: null, ranking: null },
  ],
  tournament: {
    id: 'trn_itf',
    name: 'W15 Hurghada',
    tour: null,
    circuit: 'itf',
    gender: 'women',
    discipline: 'doubles',
  },
  scheduled_at: '2026-09-12T12:00:00Z',
  round: '1/8-finals',
  surface: null,
  indoor: null,
  format: null,
  live_state: null,
  winner_player_id: null,
  freshness: {
    provider: 'fake',
    source_updated_at: null,
    observed_at: '2026-09-09T12:00:00Z',
    is_stale: false,
    age_seconds: 0,
  },
}

test.describe('P2 Home filters', () => {
  test('defaults to top-tier singles against the real fake backend', async ({ page }) => {
    const catalogRequests: string[] = []
    page.on('request', (request) => {
      if (request.url().includes('/api/matches/catalog')) catalogRequests.push(request.url())
    })

    await page.goto('/')

    await expect(page.getByRole('group', { name: '赛事级别' })).toBeVisible()
    await expect(page.getByRole('button', { name: /ATP/ })).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByRole('button', { name: /WTA/ })).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByRole('button', { name: /单打/ })).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByRole('button', { name: /Challenger/ })).toHaveAttribute('aria-pressed', 'false')

    // The fake backend dataset is ATP men's singles and must be visible by default.
    await expect(page.getByText('ATP Finals').first()).toBeVisible()
    await expect(page.getByRole('link', { name: '打开比赛' }).first()).toBeVisible()

    await expect.poll(() => catalogRequests.length).toBeGreaterThanOrEqual(2)
    const liveRequest = catalogRequests.find((url) => url.includes('status=live'))
    const upcomingRequest = catalogRequests.find((url) => url.includes('status=upcoming'))
    for (const url of [liveRequest, upcomingRequest]) {
      expect(url).toBeDefined()
      expect(url).toContain('circuit=atp')
      expect(url).toContain('circuit=wta')
      expect(url).toContain('discipline=singles')
      expect(url).not.toContain('gender=')
    }
  })

  test('stacked ITF women doubles filter shows exactly the filtered match', async ({ page }) => {
    await page.route('**/api/matches/catalog**', (route) => {
      const url = new URL(route.request().url())
      const circuits = url.searchParams.getAll('circuit')
      const genders = url.searchParams.getAll('gender')
      const disciplines = url.searchParams.getAll('discipline')
      const stacked =
        circuits.join(',') === 'itf' &&
        genders.join(',') === 'women' &&
        disciplines.join(',') === 'doubles'
      const status = (url.searchParams.get('status') ?? 'upcoming') as 'live' | 'upcoming'
      const catalog: MatchCatalogDto = {
        status,
        matches: stacked && status === 'upcoming' ? [ITF_WOMEN_DOUBLES] : [],
        filters: {
          circuits: circuits as MatchCatalogDto['filters']['circuits'],
          genders: genders as MatchCatalogDto['filters']['genders'],
          disciplines: disciplines as MatchCatalogDto['filters']['disciplines'],
        },
        facet_counts: FACET_ONE_COUNTS,
        featured_match_id: stacked && status === 'upcoming' ? ITF_WOMEN_DOUBLES.id : null,
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: catalog }),
      })
    })

    await page.goto('/')
    await expect(page.getByRole('group', { name: '赛事级别' })).toBeVisible()

    // Unselect the defaults, then stack the exact ITF women doubles combination.
    await page.getByRole('button', { name: /ATP/ }).click()
    await page.getByRole('button', { name: /WTA/ }).click()
    await page.getByRole('button', { name: /ITF/ }).click()
    await page.getByRole('button', { name: /女子/ }).click()
    await page.getByRole('button', { name: /双打/ }).click()
    await page.getByRole('button', { name: /单打/ }).click()

    await expect(page.getByRole('button', { name: /ITF/ })).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByRole('button', { name: /女子/ })).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByRole('button', { name: /双打/ })).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByRole('button', { name: /单打/ })).toHaveAttribute('aria-pressed', 'false')

    await expect(page.getByText('Hontama/ Kubka')).toBeVisible()
    await expect(page.getByRole('link', { name: '打开比赛' })).toHaveAttribute(
      'href',
      '/matches/mat_itf_women_doubles',
    )
    await expect(page.getByText('W15 Hurghada').first()).toBeVisible()
  })

  test('恢复默认 restores ATP+WTA/all-genders/singles', async ({ page }) => {
    const catalogRequests: string[] = []
    page.on('request', (request) => {
      if (request.url().includes('/api/matches/catalog')) catalogRequests.push(request.url())
    })
    await page.route('**/api/matches/catalog**', (route) => {
      const url = new URL(route.request().url())
      const catalog: MatchCatalogDto = {
        status: (url.searchParams.get('status') ?? 'upcoming') as 'live' | 'upcoming',
        matches: [],
        filters: {
          circuits: url.searchParams.getAll('circuit') as MatchCatalogDto['filters']['circuits'],
          genders: url.searchParams.getAll('gender') as MatchCatalogDto['filters']['genders'],
          disciplines: url.searchParams.getAll('discipline') as MatchCatalogDto['filters']['disciplines'],
        },
        facet_counts: FACET_ONE_COUNTS,
        featured_match_id: null,
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: catalog }),
      })
    })

    await page.goto('/')
    await expect(page.getByRole('group', { name: '赛事级别' })).toBeVisible()

    await page.getByRole('button', { name: /WTA/ }).click()
    const reset = page.getByRole('button', { name: '恢复默认' })
    await expect(reset).toBeVisible()
    await reset.click()

    await expect(page.getByRole('button', { name: /ATP/ })).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByRole('button', { name: /WTA/ })).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByRole('button', { name: /单打/ })).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByRole('button', { name: /女子/ })).toHaveAttribute('aria-pressed', 'false')
    await expect(page.getByRole('button', { name: '恢复默认' })).toHaveCount(0)

    await expect
      .poll(() => {
        const last = catalogRequests[catalogRequests.length - 1] ?? ''
        return last.includes('circuit=atp') && last.includes('circuit=wta') && last.includes('discipline=singles') && !last.includes('gender=')
      })
      .toBe(true)
  })
})
