'use client'

import { useMemo, useState } from 'react'
import { Check, UsersRound } from 'lucide-react'
import { cn, Input, useDebouncedValue } from '@f0rge/ui'
import { PeerAvatar } from '@/components/people/peer-avatar'
import type { ConnectionItem, GroupListItem } from '@/lib/api/types/social'
import type { PhotoMealTagItem } from '@/lib/api/hooks/photos'

const LIST_CAP = 15

export interface RecentTagHandle {
  handle: string
  avatar_default_index: number
  display_name: string | null
}

interface TagPeoplePickerBaseProps {
  connections: ConnectionItem[]
  groups?: GroupListItem[]
  recentHandles?: RecentTagHandle[]
  disabled?: boolean
  busyHandle?: string | null
  busyGroupId?: string | null
}

interface LocalTagPeoplePickerProps extends TagPeoplePickerBaseProps {
  mode: 'local'
  selectedHandles: string[]
  selectedGroupIds: string[]
  onChangeHandles: (handles: string[]) => void
  onChangeGroupIds: (groupIds: string[]) => void
}

interface RemoteTagPeoplePickerProps extends TagPeoplePickerBaseProps {
  mode: 'remote'
  taggedTags: PhotoMealTagItem[]
  onAddHandle: (handle: string) => void
  onRemoveTag: (tagId: string) => void
  onAddGroup: (groupId: string) => void
}

export type TagPeoplePickerProps = LocalTagPeoplePickerProps | RemoteTagPeoplePickerProps

function matchesQuery(text: string, query: string): boolean {
  return text.toLowerCase().includes(query)
}

function isCancellableStatus(status: string): boolean {
  return status === 'pending_analysis' || status === 'pending_approval'
}

function SectionLabel({ children }: { children: string }) {
  return <p className="px-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{children}</p>
}

function SelectRow({
  label,
  sublabel,
  avatar,
  selected,
  disabled,
  busy,
  onClick,
}: {
  label: string
  sublabel?: string | null
  avatar: React.ReactNode
  selected: boolean
  disabled?: boolean
  busy?: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      disabled={disabled || busy}
      onClick={onClick}
      aria-pressed={selected}
      className={cn(
        'flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left transition-colors',
        selected ? 'border-primary bg-primary/10' : 'border-muted hover:bg-muted/50',
        (disabled || busy) && 'opacity-50',
      )}
    >
      {avatar}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{label}</p>
        {sublabel && <p className="truncate text-xs text-muted-foreground">{sublabel}</p>}
      </div>
      {selected && <Check className="size-4 shrink-0 text-primary" aria-hidden />}
    </button>
  )
}

export function TagPeoplePicker(props: TagPeoplePickerProps) {
  const { connections, groups = [], recentHandles = [], disabled, busyHandle, busyGroupId } = props
  const [searchInput, setSearchInput] = useState('')
  const search = useDebouncedValue(searchInput, 300).trim().toLowerCase()

  const taggedByHandle = useMemo(() => {
    if (props.mode !== 'remote') return new Map<string, PhotoMealTagItem>()
    const map = new Map<string, PhotoMealTagItem>()
    for (const tag of props.taggedTags) {
      if (tag.user.handle) map.set(tag.user.handle, tag)
    }
    return map
  }, [props])

  const isHandleSelected = (handle: string) => {
    if (props.mode === 'local') return props.selectedHandles.includes(handle)
    return taggedByHandle.has(handle)
  }

  const isGroupSelected = (groupId: string) => {
    if (props.mode === 'local') return props.selectedGroupIds.includes(groupId)
    return false
  }

  const toggleHandle = (handle: string) => {
    if (disabled) return
    if (props.mode === 'local') {
      if (props.selectedHandles.includes(handle)) {
        props.onChangeHandles(props.selectedHandles.filter((h) => h !== handle))
      } else {
        props.onChangeHandles([...props.selectedHandles, handle])
      }
      return
    }
    const existing = taggedByHandle.get(handle)
    if (existing) {
      if (isCancellableStatus(existing.status)) {
        props.onRemoveTag(existing.id)
      }
      return
    }
    props.onAddHandle(handle)
  }

  const toggleGroup = (groupId: string) => {
    if (disabled) return
    if (props.mode === 'local') {
      if (props.selectedGroupIds.includes(groupId)) {
        props.onChangeGroupIds(props.selectedGroupIds.filter((id) => id !== groupId))
      } else {
        props.onChangeGroupIds([...props.selectedGroupIds, groupId])
      }
      return
    }
    if (!isGroupSelected(groupId)) {
      props.onAddGroup(groupId)
    }
  }

  const connectionByHandle = useMemo(() => {
    const map = new Map<string, ConnectionItem>()
    for (const item of connections) {
      map.set(item.user.handle, item)
    }
    return map
  }, [connections])

  const filteredRecent = useMemo(() => {
    if (search.length > 0) return []
    return recentHandles
      .filter((r) => connectionByHandle.has(r.handle) || connections.some((c) => c.user.handle === r.handle))
      .slice(0, 8)
  }, [recentHandles, search, connections, connectionByHandle])

  const filteredConnections = useMemo(() => {
    const recentSet = new Set(filteredRecent.map((r) => r.handle))
    let list = connections.filter((c) => !recentSet.has(c.user.handle))
    if (search) {
      list = list.filter(
        (c) =>
          matchesQuery(c.user.handle, search) ||
          (c.user.display_name != null && matchesQuery(c.user.display_name, search)),
      )
    }
    return list.slice(0, LIST_CAP)
  }, [connections, search, filteredRecent])

  const filteredGroups = useMemo(() => {
    let list = groups
    if (search) {
      list = list.filter((g) => matchesQuery(g.name, search))
    }
    return list.slice(0, LIST_CAP)
  }, [groups, search])

  if (connections.length === 0 && groups.length === 0) return null

  const showRecent = search.length === 0 && filteredRecent.length > 0
  const showPeople = filteredConnections.length > 0
  const showGroups = filteredGroups.length > 0
  const showEmpty = search.length > 0 && !showPeople && !showGroups

  return (
    <div className="space-y-3">
      <Input
        value={searchInput}
        onChange={(e) => setSearchInput(e.target.value)}
        placeholder="Search people or groups"
        disabled={disabled}
        aria-label="Search people or groups"
      />

      {showRecent && (
        <div className="space-y-1.5">
          <SectionLabel>Recently tagged</SectionLabel>
          {filteredRecent.map((recent) => {
            const conn = connectionByHandle.get(recent.handle)
            const avatarIndex = conn?.user.avatar_default_index ?? recent.avatar_default_index
            // ponytail: RecentTagHandle has no custom-avatar flag; use the matching
            // connection's when present, else fall back to the default avatar.
            const hasCustomAvatar = conn?.user.has_custom_avatar ?? false
            const selected = isHandleSelected(recent.handle)
            const tag = taggedByHandle.get(recent.handle)
            const rowDisabled =
              props.mode === 'remote' && tag != null && !isCancellableStatus(tag.status)
            return (
              <SelectRow
                key={recent.handle}
                label={`@${recent.handle}`}
                sublabel={conn?.user.display_name ?? recent.display_name}
                avatar={
                  <PeerAvatar
                    handle={recent.handle}
                    avatarDefaultIndex={avatarIndex}
                    hasCustomAvatar={hasCustomAvatar}
                    size="sm"
                  />
                }
                selected={selected}
                disabled={disabled || rowDisabled}
                busy={busyHandle === recent.handle}
                onClick={() => toggleHandle(recent.handle)}
              />
            )
          })}
        </div>
      )}

      {showPeople && (
        <div className="space-y-1.5">
          <SectionLabel>{search ? 'People' : 'Connections'}</SectionLabel>
          {filteredConnections.map((item) => {
            const handle = item.user.handle
            const tag = taggedByHandle.get(handle)
            const rowDisabled =
              props.mode === 'remote' && tag != null && !isCancellableStatus(tag.status)
            return (
              <SelectRow
                key={item.id}
                label={`@${handle}`}
                sublabel={item.user.display_name}
                avatar={
                  <PeerAvatar
                    handle={item.user.handle}
                    avatarDefaultIndex={item.user.avatar_default_index}
                    hasCustomAvatar={item.user.has_custom_avatar}
                    size="sm"
                  />
                }
                selected={isHandleSelected(handle)}
                disabled={disabled || rowDisabled}
                busy={busyHandle === handle}
                onClick={() => toggleHandle(handle)}
              />
            )
          })}
        </div>
      )}

      {showGroups && (
        <div className="space-y-1.5">
          <SectionLabel>Groups</SectionLabel>
          {filteredGroups.map((group) => (
            <SelectRow
              key={group.id}
              label={group.name}
              sublabel={`${group.member_count} members`}
              avatar={
                <span className="flex size-8 items-center justify-center rounded-full bg-muted">
                  <UsersRound className="size-4 text-muted-foreground" />
                </span>
              }
              selected={isGroupSelected(group.id)}
              disabled={disabled}
              busy={busyGroupId === group.id}
              onClick={() => toggleGroup(group.id)}
            />
          ))}
        </div>
      )}

      {showEmpty && (
        <p className="px-1 text-sm text-muted-foreground">No matches for &ldquo;{search}&rdquo;.</p>
      )}
    </div>
  )
}
