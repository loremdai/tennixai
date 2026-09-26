import { UserRound } from 'lucide-react'

import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { cn } from '@/lib/utils'

export function PlayerAvatar({
  name,
  imageUrl,
  className,
  fallbackClassName,
}: {
  name: string
  imageUrl?: string | null
  className?: string
  fallbackClassName?: string
}) {
  return (
    <Avatar
      role="img"
      aria-label={`${name} 头像`}
      className={cn('size-9', className)}
    >
      {imageUrl ? <AvatarImage src={imageUrl} alt="" aria-hidden="true" /> : null}
      <AvatarFallback className={fallbackClassName}>
        <UserRound aria-hidden="true" className="size-1/2" />
      </AvatarFallback>
    </Avatar>
  )
}
