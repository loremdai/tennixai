import { HomePage } from '@/components/home-page'
import { parseHomePulseState } from '@/components/p3/p3-preview-data'

type PageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}

/** Server-side P3 capability probe. Runs off-browser so a P3-disabled
 * deployment never produces failing client requests (and never changes the
 * P1/P2 Home visuals). Any failure degrades to "not enabled". */
async function probeP3Enabled(): Promise<boolean> {
  const baseUrl = process.env.TENNIX_BACKEND_URL
  if (!baseUrl) return false
  try {
    const response = await fetch(`${baseUrl}/api/v1/markets/pulse`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(1500),
    })
    return response.status === 200
  } catch {
    return false
  }
}

export default async function Page({ searchParams }: PageProps) {
  const params = await searchParams
  const previewValue = Array.isArray(params.preview) ? params.preview[0] : params.preview
  const previewP3 = previewValue === 'p3'
  const value = params.q
  const question = previewP3 ? undefined : Array.isArray(value) ? value[0] : value
  // ?p3=1 force-enables the live pulse (same URL-mode pattern as
  // ?preview=p3) for e2e/dev; production otherwise trusts the server probe.
  const p3Param = Array.isArray(params.p3) ? params.p3[0] : params.p3
  const p3Enabled = previewP3 ? false : p3Param === '1' || (await probeP3Enabled())

  return (
    <HomePage
      key={`${question ?? ''}-${previewP3 ? 'p3' : 'default'}`}
      initialQuestion={question}
      previewP3={previewP3}
      initialPulseState={parseHomePulseState(params.pulse)}
      p3Enabled={p3Enabled}
    />
  )
}
