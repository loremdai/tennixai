import { ProductHeader } from '@/components/match/match-header'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'

function LoadingBar({ className }: { className: string }) {
  return <div className={cn('animate-pulse rounded-md bg-muted', className)} />
}

export default function Loading() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <ProductHeader active="markets" marketsHref="/markets?preview=p3" />
      <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 md:px-6 md:py-8" aria-busy="true" aria-label="正在加载市场决策支持">
        <section className="flex flex-col gap-3 border-b pb-6">
          <LoadingBar className="h-4 w-48" />
          <LoadingBar className="h-10 w-72 max-w-full" />
          <LoadingBar className="h-5 w-full max-w-2xl" />
        </section>
        <LoadingBar className="h-20 w-full rounded-xl" />
        <LoadingBar className="h-16 w-full rounded-xl" />
        <div className="grid gap-3">
          {[0, 1, 2].map((item) => (
            <Card key={item} size="sm">
              <CardContent className="grid min-h-28 grid-cols-2 items-center gap-4 py-1 md:grid-cols-5">
                <LoadingBar className="col-span-2 h-14 md:col-span-1" />
                <LoadingBar className="h-12" />
                <LoadingBar className="h-12" />
                <LoadingBar className="h-12" />
                <LoadingBar className="h-9" />
              </CardContent>
            </Card>
          ))}
        </div>
      </main>
    </div>
  )
}
