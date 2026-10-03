'use client'

import { useState } from 'react'
import { Avatar, AvatarFallback, AvatarImage, cn } from '@f0rge/ui'

interface PeerAvatarProps {
  handle: string
  avatarDefaultIndex: number
  hasCustomAvatar?: boolean
  size?: 'sm' | 'md'
  className?: string
}

const SIZE_CLASS = {
  sm: 'size-8',
  md: 'size-10',
} as const

export function PeerAvatar({
  handle,
  avatarDefaultIndex,
  hasCustomAvatar = false,
  size = 'sm',
  className,
}: PeerAvatarProps) {
  const [failed, setFailed] = useState(false)
  const defaultSrc = `/avatars/defaults/${String(avatarDefaultIndex).padStart(2, '0')}.svg`
  const customSrc = `/api/v1/social/users/${handle}/avatar`

  return (
    <Avatar className={cn(SIZE_CLASS[size], className)}>
      {hasCustomAvatar && handle && !failed ? (
        <AvatarImage src={customSrc} alt="" onError={() => setFailed(true)} />
      ) : (
        <AvatarImage src={defaultSrc} alt="" />
      )}
      <AvatarFallback aria-hidden />
    </Avatar>
  )
}
