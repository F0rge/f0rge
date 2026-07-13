'use client'

import { cn } from '@f0rge/ui'
import { UsersRound } from 'lucide-react'
import { PeerAvatar } from '@/components/people/peer-avatar'
import type { ConnectionItem, GroupListItem } from '@/lib/api/types/social'

interface TagPeoplePickerProps {
  connections: ConnectionItem[]
  groups?: GroupListItem[]
  selectedHandles: string[]
  selectedGroupIds: string[]
  onChangeHandles: (handles: string[]) => void
  onChangeGroupIds: (groupIds: string[]) => void
  disabled?: boolean
}

export function TagPeoplePicker({
  connections,
  groups = [],
  selectedHandles,
  selectedGroupIds,
  onChangeHandles,
  onChangeGroupIds,
  disabled = false,
}: TagPeoplePickerProps) {
  if (connections.length === 0 && groups.length === 0) return null

  const toggleHandle = (handle: string) => {
    if (disabled) return
    if (selectedHandles.includes(handle)) {
      onChangeHandles(selectedHandles.filter((h) => h !== handle))
      return
    }
    onChangeHandles([...selectedHandles, handle])
  }

  const toggleGroup = (groupId: string) => {
    if (disabled) return
    if (selectedGroupIds.includes(groupId)) {
      onChangeGroupIds(selectedGroupIds.filter((id) => id !== groupId))
      return
    }
    onChangeGroupIds([...selectedGroupIds, groupId])
  }

  return (
    <div className="space-y-3">
      {groups.length > 0 && (
        <div>
          <p className="mb-1.5 text-xs font-medium text-muted-foreground">Tag a group</p>
          <div className="flex flex-wrap gap-1.5">
            {groups.map((group) => {
              const isSelected = selectedGroupIds.includes(group.id)
              return (
                <button
                  key={group.id}
                  type="button"
                  disabled={disabled}
                  onClick={() => toggleGroup(group.id)}
                  aria-pressed={isSelected}
                  className={cn(
                    'inline-flex min-h-[36px] items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors',
                    isSelected
                      ? 'border-primary bg-primary text-primary-foreground'
                      : 'border-border bg-background text-muted-foreground hover:bg-muted hover:text-foreground',
                    disabled && 'opacity-50',
                  )}
                >
                  <UsersRound className="size-3.5" />
                  {group.name}
                  <span className="opacity-80">({group.member_count})</span>
                </button>
              )
            })}
          </div>
        </div>
      )}

      {connections.length > 0 && (
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
                  onClick={() => toggleHandle(handle)}
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
      )}
    </div>
  )
}
