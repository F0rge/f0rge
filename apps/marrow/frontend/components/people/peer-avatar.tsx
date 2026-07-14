'use client'

import { useState } from 'react'
import Image from 'next/image'
import { cn } from '@f0rge/ui'

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

const SIZE_PX = {
  sm: 32,
  md: 40,
} as const

export function PeerAvatar({
  handle,
  avatarDefaultIndex,
  hasCustomAvatar = false,
  size = 'sm',
  className,
}: PeerAvatarProps) {
  const [failed, setFailed] = useState(false)
  const px = SIZE_PX[size]

  if (hasCustomAvatar && handle && !failed) {
    return (
      <Image
        src={`/api/v1/social/users/${handle}/avatar`}
        alt=""
        width={px}
        height={px}
        unoptimized
        onError={() => setFailed(true)}
        className={cn('rounded-full bg-muted object-cover', SIZE_CLASS[size], className)}
      />
    )
  }

  const src = `/avatars/defaults/${String(avatarDefaultIndex).padStart(2, '0')}.svg`
  return (
    <Image
      src={src}
      alt=""
      width={px}
      height={px}
      className={cn('rounded-full bg-muted object-cover', SIZE_CLASS[size], className)}
    />
  )
}
