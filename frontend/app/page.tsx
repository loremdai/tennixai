import { HomePage } from '@/components/home-page'
import { parseHomePulseState } from '@/components/p3/p3-preview-data'

type PageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}

export default async function Page({ searchParams }: PageProps) {
  const params = await searchParams
  const previewValue = Array.isArray(params.preview) ? params.preview[0] : params.preview
  const previewP3 = previewValue === 'p3'
  const value = params.q
  const question = previewP3 ? undefined : Array.isArray(value) ? value[0] : value

  return (
    <HomePage
      key={`${question ?? ''}-${previewP3 ? 'p3' : 'default'}`}
      initialQuestion={question}
      previewP3={previewP3}
      initialPulseState={parseHomePulseState(params.pulse)}
    />
  )
}
