import { HomePage } from '@/components/home-page'

type PageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}

export default async function Page({ searchParams }: PageProps) {
  const params = await searchParams
  const value = params.q
  const question = Array.isArray(value) ? value[0] : value

  return <HomePage key={question} initialQuestion={question} />
}
