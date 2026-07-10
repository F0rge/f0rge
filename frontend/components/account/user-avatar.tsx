'use client'

import Image from 'next/image'
import { useAccount, useAvatarCacheBust } from '@/lib/api/hooks'
import { cn } from '@/lib/utils'

interface UserAvatarProps {
  size?: 'sm' | 'md'
  className?: string
}

const SIZE_CLASS = {
  sm: 'size-9',
  md: 'size-16',
} as const

const SIZE_PX = {
  sm: 36,
  md: 64,
} as const

export function UserAvatar({ size = 'sm', className }: UserAvatarProps) {
  const account = useAccount()
  const cacheBust = useAvatarCacheBust()
  const data = account.data

  if (!data) {
    return (
      <span
        className={cn(
          'inline-flex items-center justify-center rounded-full border border-border bg-muted',
          SIZE_CLASS[size],
          className,
        )}
        aria-hidden
      />
    )
  }

  if (data.has_custom_avatar) {
    return (
      <Image
        src={`/api/v1/account/avatar?v=${cacheBust.data ?? 0}`}
        alt=""
        width={SIZE_PX[size]}
        height={SIZE_PX[size]}
        unoptimized
        className={cn('rounded-full border border-border object-cover', SIZE_CLASS[size], className)}
      />
    )
  }

  const index = String(data.avatar_default_index).padStart(2, '0')

  return (
    <Image
      src={`/avatars/defaults/${index}.svg`}
      alt=""
      width={SIZE_PX[size]}
      height={SIZE_PX[size]}
      className={cn('rounded-full border border-border', SIZE_CLASS[size], className)}
    />
  )
}
