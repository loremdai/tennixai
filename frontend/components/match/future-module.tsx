import { Info } from 'lucide-react'

type FutureModuleProps = {
  title: string
  description: string
}

export function FutureModule({
  title,
  description,
}: FutureModuleProps) {
  return (
    <div className="flex min-h-28 items-start gap-3 rounded-lg bg-muted/25 p-4">
      <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
      <div className="flex flex-col gap-1">
        <p className="font-medium text-foreground">{title}</p>
        <p className="max-w-md text-sm leading-relaxed text-muted-foreground">{description}</p>
      </div>
    </div>
  )
}
