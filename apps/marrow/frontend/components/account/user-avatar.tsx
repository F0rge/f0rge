'use client'

import { useState } from 'react'
import { Avatar, AvatarFallback, AvatarImage, cn } from '@f0rge/ui'
import { useAccount, useAvatarCacheBust } from '@/lib/api/hooks'

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

export function UserAvatar({ size = 'sm', className }: UserAvatarProps) {
  const account = useAccount()
  const cacheBust = useAvatarCacheBust()
  const data = account.data
  const [failed, setFailed] = useState(false)

  const sizeClass = SIZE_CLASS[size]
  const index = data ? String(data.avatar_default_index).padStart(2, '0') : '00'
  const defaultSrc = `/avatars/defaults/${index}.svg`

  return (
    <Avatar className={cn(sizeClass, className)}>
      {data?.has_custom_avatar && !failed ? (
        <AvatarImage
          src={`/api/v1/account/avatar?v=${cacheBust.data ?? 0}`}
          alt=""
          onError={() => setFailed(true)}
        />
      ) : (
        <AvatarImage src={defaultSrc} alt="" />
      )}
      <AvatarFallback aria-hidden />
    </Avatar>
  )
}
