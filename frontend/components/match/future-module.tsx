import { LockKeyhole, Radio } from 'lucide-react'

import { Badge } from '@/components/ui/badge'

type FutureModuleProps = {
  phase: 'P2' | 'P3'
  title: string
  description: string
}

export function FutureModule({
  phase,
  title,
  description,
}: FutureModuleProps) {
  return (
    <div className="flex min-h-32 flex-col items-center justify-center gap-3 rounded-lg border border-dashed bg-muted/20 p-6 text-center">
      <div className="flex size-10 items-center justify-center rounded-full bg-secondary text-muted-foreground">
        {phase === 'P2' ? (
          <Radio aria-hidden="true" className="size-5" />
        ) : (
          <LockKeyhole aria-hidden="true" className="size-5" />
        )}
      </div>
      <div className="flex flex-col items-center gap-1">
        <Badge variant="outline">{phase} 解锁</Badge>
        <p className="font-medium text-foreground">{title}</p>
        <p className="max-w-md text-sm leading-relaxed text-muted-foreground">
          {description}
        </p>
      </div>
    </div>
  )
}
