'use client'

import { useMemo, useState } from 'react'
import { TagPeoplePicker, type RecentTagHandle } from '@/components/checkin/tag-people-picker'
import { PeerAvatar } from '@/components/people/peer-avatar'
import { useAddPhotoTags, usePhotoTags } from '@/lib/api/hooks/photos'
import {
  useCancelMealTag,
  useConnections,
  useGroups,
  useMealTags,
} from '@/lib/api/hooks/social'
import { getErrorDetail } from '@f0rge/ui/api'
import { toast } from 'sonner'
import type { Photo } from '@/lib/api/types'

interface MealCompanionsSectionProps {
  photo: Photo
  /** Compact row for meal card thumbnails; full editor in photo overlay. */
  variant?: 'compact' | 'editor'
}

function formatWithLine(handles: string[]): string {
  if (handles.length === 0) return ''
  if (handles.length === 1) return `@${handles[0]}`
  if (handles.length === 2) return `@${handles[0]} and @${handles[1]}`
  return `@${handles.slice(0, -1).join(', @')}, and @${handles[handles.length - 1]}`
}

export function MealCompanionsSection({ photo, variant = 'editor' }: MealCompanionsSectionProps) {
  const isSharedCopy = photo.source_photo_id != null || Boolean(photo.tagged_by_handle)
  const tags = usePhotoTags(photo.id, !isSharedCopy)
  const connections = useConnections()
  const groups = useGroups()
  const mealTags = useMealTags()
  const addTags = useAddPhotoTags()
  const cancelTag = useCancelMealTag()
  const [busyHandle, setBusyHandle] = useState<string | null>(null)
  const [busyGroupId, setBusyGroupId] = useState<string | null>(null)

  const taggedHandles = useMemo(() => {
    const fromApi = tags.data?.tags.map((t) => t.user.handle).filter(Boolean) ?? []
    const fromEntry = photo.tagged_with_handles ?? []
    return fromApi.length > 0 ? fromApi : fromEntry
  }, [photo.tagged_with_handles, tags.data?.tags])

  const acceptedConnections = connections.data?.accepted ?? []

  const availableGroups = useMemo(
    () => (groups.data ?? []).filter((g) => g.my_status === 'joined'),
    [groups.data],
  )

  const recentHandles = useMemo((): RecentTagHandle[] => {
    const seen = new Set<string>()
    const recent: RecentTagHandle[] = []
    for (const tag of mealTags.data?.outgoing ?? []) {
      const handle = tag.tagged_user.handle
      if (!handle || seen.has(handle)) continue
      seen.add(handle)
      recent.push({
        handle,
        avatar_default_index: tag.tagged_user.avatar_default_index,
        display_name: tag.tagged_user.display_name,
      })
      if (recent.length >= 8) break
    }
    return recent
  }, [mealTags.data?.outgoing])

  const canTag =
    !isSharedCopy &&
    (acceptedConnections.length > 0 || availableGroups.length > 0)

  if (variant === 'compact') {
    if (taggedHandles.length === 0 && !photo.tagged_by_handle) return null
    return (
      <p className="mt-0.5 truncate text-xs text-muted-foreground">
        {photo.tagged_by_handle ? (
          <>from @{photo.tagged_by_handle}</>
        ) : (
          <>With {formatWithLine(taggedHandles)}</>
        )}
      </p>
    )
  }

  const onAddHandle = async (handle: string) => {
    setBusyHandle(handle)
    try {
      await addTags.mutateAsync({ photoId: photo.id, handles: [handle] })
    } catch (err) {
      toast.error(getErrorDetail(err, 'Could not tag person'))
    } finally {
      setBusyHandle(null)
    }
  }

  const onAddGroup = async (groupId: string) => {
    setBusyGroupId(groupId)
    try {
      await addTags.mutateAsync({ photoId: photo.id, handles: [], groupIds: [groupId] })
      toast.success('Group tagged')
    } catch (err) {
      toast.error(getErrorDetail(err, 'Could not tag group'))
    } finally {
      setBusyGroupId(null)
    }
  }

  const onRemoveTag = async (tagId: string) => {
    try {
      await cancelTag.mutateAsync(tagId)
    } catch (err) {
      toast.error(getErrorDetail(err, 'Could not remove tag'))
    }
  }

  const taggedTags = tags.data?.tags ?? []
  const isBusy = addTags.isPending || cancelTag.isPending

  return (
    <div className="space-y-3 rounded-lg border border-border bg-muted/30 p-3">
      <div>
        <p className="text-xs font-medium text-muted-foreground">With</p>
        {taggedHandles.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {taggedTags.length > 0
              ? taggedTags.map((tag) => (
                  <span
                    key={tag.id}
                    className="inline-flex items-center gap-1 rounded-full border border-border bg-background px-2 py-0.5 text-xs font-medium"
                  >
                    <PeerAvatar avatarDefaultIndex={tag.user.avatar_default_index} size="sm" className="size-4" />
                    @{tag.user.handle}
                  </span>
                ))
              : taggedHandles.map((handle) => (
                  <span
                    key={handle}
                    className="inline-flex items-center rounded-full border border-border bg-background px-2 py-0.5 text-xs font-medium"
                  >
                    @{handle}
                  </span>
                ))}
          </div>
        ) : (
          <p className="mt-1 text-xs text-muted-foreground">Just you — tag connected people below.</p>
        )}
        {photo.tagged_by_handle && (
          <p className="mt-1 text-xs text-muted-foreground">Shared from @{photo.tagged_by_handle}</p>
        )}
      </div>

      {canTag && (
        <TagPeoplePicker
          mode="remote"
          connections={acceptedConnections}
          groups={availableGroups}
          recentHandles={recentHandles}
          taggedTags={taggedTags}
          onAddHandle={(handle) => void onAddHandle(handle)}
          onRemoveTag={(tagId) => void onRemoveTag(tagId)}
          onAddGroup={(groupId) => void onAddGroup(groupId)}
          disabled={isBusy}
          busyHandle={busyHandle}
          busyGroupId={busyGroupId}
        />
      )}
    </div>
  )
}
