'use client'

import { useMemo, useState } from 'react'
import { Button } from '@f0rge/ui'
import { TagPeoplePicker } from '@/components/checkin/tag-people-picker'
import { PeerAvatar } from '@/components/people/peer-avatar'
import { useAddPhotoTags, usePhotoTags } from '@/lib/api/hooks/photos'
import { useConnections } from '@/lib/api/hooks/social'
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
  const addTags = useAddPhotoTags()
  const [pendingHandles, setPendingHandles] = useState<string[]>([])

  const taggedHandles = useMemo(() => {
    const fromApi = tags.data?.tags.map((t) => t.user.handle).filter(Boolean) ?? []
    const fromEntry = photo.tagged_with_handles ?? []
    return fromApi.length > 0 ? fromApi : fromEntry
  }, [photo.tagged_with_handles, tags.data?.tags])

  const taggedSet = useMemo(() => new Set(taggedHandles), [taggedHandles])

  const availableConnections = useMemo(
    () =>
      (connections.data?.accepted ?? []).filter((c) => !taggedSet.has(c.user.handle)),
    [connections.data?.accepted, taggedSet],
  )

  const canTag = !isSharedCopy && (connections.data?.accepted.length ?? 0) > 0

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

  const onSaveTags = async () => {
    if (pendingHandles.length === 0) return
    try {
      await addTags.mutateAsync({ photoId: photo.id, handles: pendingHandles })
      setPendingHandles([])
      toast.success('People tagged')
    } catch (err) {
      toast.error(getErrorDetail(err, 'Could not tag people'))
    }
  }

  return (
    <div className="space-y-3 rounded-lg border border-border bg-muted/30 p-3">
      <div>
        <p className="text-xs font-medium text-muted-foreground">With</p>
        {taggedHandles.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {tags.data?.tags.map((tag) => (
              <span
                key={tag.id}
                className="inline-flex items-center gap-1 rounded-full border border-border bg-background px-2 py-0.5 text-xs font-medium"
              >
                <PeerAvatar avatarDefaultIndex={tag.user.avatar_default_index} size="sm" className="size-4" />
                @{tag.user.handle}
              </span>
            )) ??
              taggedHandles.map((handle) => (
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
        <>
          <TagPeoplePicker
            connections={availableConnections}
            selectedHandles={pendingHandles}
            onChange={setPendingHandles}
            disabled={addTags.isPending}
          />
          {pendingHandles.length > 0 && (
            <Button
              type="button"
              size="sm"
              onClick={onSaveTags}
              disabled={addTags.isPending}
              className="w-full sm:w-auto"
            >
              {addTags.isPending ? 'Tagging...' : `Tag ${pendingHandles.length}`}
            </Button>
          )}
        </>
      )}
    </div>
  )
}
