import Image from 'next/image'
import { cn } from '@f0rge/ui'

interface PeerAvatarProps {
  avatarDefaultIndex: number
  size?: 'sm' | 'md'
  className?: string
}

const SIZE_CLASS = {
  sm: 'size-8',
  md: 'size-10',
} as const

export function PeerAvatar({ avatarDefaultIndex, size = 'sm', className }: PeerAvatarProps) {
  const src = `/avatars/defaults/${String(avatarDefaultIndex).padStart(2, '0')}.svg`
  return (
    <Image
      src={src}
      alt=""
      width={size === 'sm' ? 32 : 40}
      height={size === 'sm' ? 32 : 40}
      className={cn('rounded-full bg-muted object-cover', SIZE_CLASS[size], className)}
    />
  )
}
