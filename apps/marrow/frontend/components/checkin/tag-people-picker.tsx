'use client'

import { cn } from '@f0rge/ui'
import { PeerAvatar } from '@/components/people/peer-avatar'
import type { ConnectionItem } from '@/lib/api/types/social'

interface TagPeoplePickerProps {
  connections: ConnectionItem[]
  selectedHandles: string[]
  onChange: (handles: string[]) => void
  disabled?: boolean
}

export function TagPeoplePicker({
  connections,
  selectedHandles,
  onChange,
  disabled = false,
}: TagPeoplePickerProps) {
  if (connections.length === 0) return null

  const toggle = (handle: string) => {
    if (disabled) return
    if (selectedHandles.includes(handle)) {
      onChange(selectedHandles.filter((h) => h !== handle))
      return
    }
    onChange([...selectedHandles, handle])
  }

  return (
    <div>
      <p className="mb-1.5 text-xs font-medium text-muted-foreground">Tag people</p>
      <div className="flex flex-wrap gap-1.5">
        {connections.map((item) => {
          const handle = item.user.handle
          const isSelected = selectedHandles.includes(handle)
          return (
            <button
              key={item.id}
              type="button"
              disabled={disabled}
              onClick={() => toggle(handle)}
              aria-pressed={isSelected}
              className={cn(
                'inline-flex min-h-[36px] items-center gap-1.5 rounded-full border px-2 py-1 text-xs font-medium transition-colors',
                isSelected
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'border-border bg-background text-muted-foreground hover:bg-muted hover:text-foreground',
                disabled && 'opacity-50',
              )}
            >
              <PeerAvatar avatarDefaultIndex={item.user.avatar_default_index} size="sm" className="size-5" />
              @{handle}
            </button>
          )
        })}
      </div>
    </div>
  )
}
