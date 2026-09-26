import { cn } from '@/lib/utils'

export type PlayerNameProps = {
  name: string
  localizedName?: string | null
  className?: string
  primaryClassName?: string
  secondaryClassName?: string
}

export function PlayerName({
  name,
  localizedName,
  className,
  primaryClassName,
  secondaryClassName,
}: PlayerNameProps) {
  const localized = localizedName?.trim()

  return (
    <span className={cn('inline-flex min-w-0 flex-col align-top leading-tight', className)}>
      <span className={cn('block min-w-0 truncate', primaryClassName)}>{name}</span>
      {localized ? (
        <span className={cn('block min-w-0 truncate text-xs text-muted-foreground', secondaryClassName)}>
          {localized}
        </span>
      ) : null}
    </span>
  )
}
