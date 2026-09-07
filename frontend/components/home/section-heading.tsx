import type { ReactNode } from 'react'

type SectionHeadingProps = {
  headingId: string
  eyebrow: string
  title: string
  description: string
  action?: ReactNode
}

export function SectionHeading({
  headingId,
  eyebrow,
  title,
  description,
  action,
}: SectionHeadingProps) {
  return (
    <header className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
      <div className="flex flex-col gap-1">
        <p className="font-mono text-xs font-semibold uppercase tracking-widest text-primary">
          {eyebrow}
        </p>
        <h2 id={headingId} className="text-balance text-xl font-semibold tracking-tight md:text-2xl">
          {title}
        </h2>
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
          {description}
        </p>
      </div>
      {action}
    </header>
  )
}
