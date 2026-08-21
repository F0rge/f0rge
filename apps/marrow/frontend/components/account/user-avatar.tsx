'use client'

import { useState } from 'react'
import Image from 'next/image'
import { useAccount, useAvatarCacheBust } from '@/lib/api/hooks'
import { cn } from '@f0rge/ui'

interface UserAvatarProps {
  size?: 'xs' | 'sm' | 'md' | 'lg'
  className?: string
}

const SIZE_CLASS = {
  xs: 'size-6',
  sm: 'size-9',
  md: 'size-16',
  lg: 'size-[72px]',
} as const

const SIZE_PX = {
  xs: 24,
  sm: 36,
  md: 64,
  lg: 72,
} as const

export function UserAvatar({ size = 'sm', className }: UserAvatarProps) {
  const account = useAccount()
  const cacheBust = useAvatarCacheBust()
  const data = account.data
  const [failedSrc, setFailedSrc] = useState<string | null>(null)

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

  const index = String(data.avatar_default_index).padStart(2, '0')
  const defaultSrc = `/avatars/defaults/${index}.svg`
  const customSrc = data.has_custom_avatar
    ? `/api/v1/account/avatar?v=${cacheBust.data ?? 0}`
    : null

  if (customSrc && failedSrc !== customSrc) {
    return (
      <Image
        src={customSrc}
        alt=""
        width={SIZE_PX[size]}
        height={SIZE_PX[size]}
        unoptimized
        onError={() => setFailedSrc(customSrc)}
        className={cn('rounded-full border border-border object-cover', SIZE_CLASS[size], className)}
      />
    )
  }

  return (
    <Image
      src={defaultSrc}
      alt=""
      width={SIZE_PX[size]}
      height={SIZE_PX[size]}
      className={cn('rounded-full border border-border', SIZE_CLASS[size], className)}
    />
  )
}
