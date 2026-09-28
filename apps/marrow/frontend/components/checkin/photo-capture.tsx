'use client'

import { useRef, useState, useCallback, useEffect } from 'react'
import { BookOpen, Camera, ImageIcon, X, Loader2, AlertTriangle } from 'lucide-react'
import { MealLibrarySheet } from './meal-library-sheet'
import { MealTimeChips } from './meal-time-chips'
import { TagPeoplePicker } from './tag-people-picker'
import { useUploadPhoto, useUpdatePhotoLabel } from '@/lib/api/hooks'
import { useConnections, useGroups } from '@/lib/api/hooks/social'
import { getErrorDetail } from '@f0rge/ui/api'
import { Button, cn } from '@f0rge/ui'
import { defaultMealTimeForEntry, entryLocalDate } from '@/lib/checkin/meal-time'
import { statusText } from '@/lib/ui/status'
import type { Photo } from '@/lib/api/types'

interface StagedPhoto {
  id: string
  file: File
  /** Stable object URL — created once per file, revoked on remove/unmount. */
  previewUrl: string
  label: string
  mealTime: Date
  taggedHandles: string[]
  taggedGroupIds: string[]
  status: 'staged' | 'uploading' | 'error'
  errorMessage?: string
  serverPhotoId?: number
  labelSynced?: string
}

interface PhotoCaptureProps {
  date: string
  existingPhotos: Photo[]
  ensureEntryExists: () => Promise<void>
  onEntryEnsured?: () => void
}

function generateId(): string {
  return Math.random().toString(36).slice(2)
}

export function PhotoCapture({
  date,
  existingPhotos,
  ensureEntryExists,
  onEntryEnsured,
}: PhotoCaptureProps) {
  const cameraRef = useRef<HTMLInputElement>(null)
  const galleryRef = useRef<HTMLInputElement>(null)
  const uploadPhoto = useUploadPhoto()
  const updatePhotoLabel = useUpdatePhotoLabel()
  const connections = useConnections()
  const groups = useGroups()
  const acceptedConnections = connections.data?.accepted ?? []
  const joinedGroups = (groups.data ?? []).filter((g) => g.my_status === 'joined')

  const [photos, setPhotos] = useState<StagedPhoto[]>([])
  const [libraryOpen, setLibraryOpen] = useState(false)
  // Serialize uploads so concurrent picks cannot race on backend filename allocation.
  const uploadChainRef = useRef(Promise.resolve())
  const photosRef = useRef(photos)
  useEffect(() => {
    photosRef.current = photos
  }, [photos])

  const existingPhotoIds = useRef(new Set<number>())
  useEffect(() => {
    existingPhotoIds.current = new Set(existingPhotos.map((p) => p.id))
    setPhotos((prev) => {
      const next = prev.filter((p) => {
        if (p.serverPhotoId != null && existingPhotoIds.current.has(p.serverPhotoId)) {
          URL.revokeObjectURL(p.previewUrl)
          return false
        }
        return true
      })
      return next.length === prev.length ? prev : next
    })
  }, [existingPhotos])

  useEffect(() => {
    return () => {
      for (const photo of photosRef.current) {
        URL.revokeObjectURL(photo.previewUrl)
      }
    }
  }, [])

  const enqueueUpload = useCallback((task: () => Promise<void>) => {
    const next = uploadChainRef.current.then(task, task)
    uploadChainRef.current = next.then(
      () => undefined,
      () => undefined,
    )
    return next
  }, [])

  const removePhoto = useCallback((id: string) => {
    setPhotos((prev) => {
      const target = prev.find((p) => p.id === id)
      if (target) URL.revokeObjectURL(target.previewUrl)
      return prev.filter((p) => p.id !== id)
    })
  }, [])

  const syncLabelToServer = useCallback(
    (stagedId: string, serverPhotoId: number, label: string) => {
      void updatePhotoLabel.mutateAsync({ photoId: serverPhotoId, label })
      setPhotos((prev) =>
        prev.map((p) =>
          p.id === stagedId ? { ...p, labelSynced: label } : p,
        ),
      )
    },
    [updatePhotoLabel],
  )

  const runUpload = useCallback(async (id: string) => {
    const photo = photosRef.current.find((p) => p.id === id)
    if (!photo || photo.status === 'uploading') return

    setPhotos((prev) =>
      prev.map((p) => p.id === id ? { ...p, status: 'uploading', errorMessage: undefined } : p),
    )

    await ensureEntryExists()
    onEntryEnsured?.()

    try {
      const created = await uploadPhoto.mutateAsync({
        date,
        file: photo.file,
        label: photo.label || undefined,
        mealTime: photo.mealTime,
        taggedHandles: photo.taggedHandles,
        taggedGroupIds: photo.taggedGroupIds,
      })

      setPhotos((prev) =>
        prev.map((p) =>
          p.id === id
            ? {
                ...p,
                status: 'staged',
                serverPhotoId: created.id,
                labelSynced: photo.label,
              }
            : p,
        ),
      )

      if (photo.label && photo.label !== photo.labelSynced) {
        syncLabelToServer(id, created.id, photo.label)
      }
    } catch (err) {
      const msg = getErrorDetail(err, 'Upload failed')
      setPhotos((prev) =>
        prev.map((p) =>
          p.id === id
            ? { ...p, status: 'error', errorMessage: msg }
            : p,
        ),
      )
    }
  }, [date, ensureEntryExists, onEntryEnsured, uploadPhoto, syncLabelToServer])

  const retryUpload = useCallback((id: string) => {
    void enqueueUpload(() => runUpload(id))
  }, [enqueueUpload, runUpload])

  const uploadAllStaged = useCallback(() => {
    const ids = photosRef.current
      .filter((p) => p.status === 'staged' && p.serverPhotoId == null)
      .map((p) => p.id)
    for (const id of ids) {
      void enqueueUpload(() => runUpload(id))
    }
  }, [enqueueUpload, runUpload])

  const handleFileSelect = useCallback((files: FileList | null) => {
    if (!files || files.length === 0) return
    const incoming = Array.from(files)
    const mealTime = defaultMealTimeForEntry(date)

    const staged: StagedPhoto[] = incoming.map((file) => ({
      id: generateId(),
      file,
      previewUrl: URL.createObjectURL(file),
      label: '',
      mealTime: new Date(mealTime),
      taggedHandles: [],
      taggedGroupIds: [],
      status: 'staged',
    }))
    setPhotos((prev) => [...prev, ...staged])

    if (staged.length === 1) {
      void enqueueUpload(() => runUpload(staged[0].id))
    }
  }, [date, enqueueUpload, runUpload])

  const handleLabelChange = useCallback(
    (stagedId: string, label: string) => {
      setPhotos((prev) =>
        prev.map((p) => (p.id === stagedId ? { ...p, label } : p)),
      )
      const photo = photosRef.current.find((p) => p.id === stagedId)
      if (photo?.serverPhotoId != null && label !== photo.labelSynced) {
        syncLabelToServer(stagedId, photo.serverPhotoId, label)
      }
    },
    [syncLabelToServer],
  )

  const stagedCount = photos.filter((p) => p.status === 'staged' && p.serverPhotoId == null).length

  return (
    <div className="space-y-3">
      <label className="text-sm font-medium leading-none">Add meal</label>

      <div className="grid grid-cols-3 gap-2">
        <button
          type="button"
          onClick={() => cameraRef.current?.click()}
          className="em-press flex min-h-[44px] flex-col items-center justify-center gap-1 rounded-full border border-border bg-background px-2 py-2 text-xs font-medium hover:bg-muted sm:text-sm sm:flex-row sm:gap-2"
        >
          <Camera className="size-4 shrink-0" />
          Take Photo
        </button>
        <button
          type="button"
          onClick={() => galleryRef.current?.click()}
          className="em-press flex min-h-[44px] flex-col items-center justify-center gap-1 rounded-full border border-border bg-background px-2 py-2 text-xs font-medium hover:bg-muted sm:text-sm sm:flex-row sm:gap-2"
        >
          <ImageIcon className="size-4 shrink-0" />
          Choose Photo
        </button>
        <button
          type="button"
          onClick={() => setLibraryOpen(true)}
          className="em-press flex min-h-[44px] flex-col items-center justify-center gap-1 rounded-full border border-border bg-background px-2 py-2 text-xs font-medium hover:bg-muted sm:text-sm sm:flex-row sm:gap-2"
        >
          <BookOpen className="size-4 shrink-0" />
          From library
        </button>
      </div>

      <input
        ref={cameraRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={(e) => { void handleFileSelect(e.target.files) }}
        className="hidden"
      />
      <input
        ref={galleryRef}
        type="file"
        accept="image/*"
        onChange={(e) => { void handleFileSelect(e.target.files) }}
        className="hidden"
      />

      {photos.length > 0 && (
        <div className="space-y-3">
          {stagedCount >= 2 && (
            <Button type="button" className="w-full" onClick={uploadAllStaged}>
              Upload all ({stagedCount})
            </Button>
          )}
          {photos.map((photo) => (
            <div key={photo.id} className="rounded-lg border border-border p-3 space-y-2">
              <div className="flex items-start gap-3">
                <div className="relative size-16 shrink-0 overflow-hidden rounded-md bg-muted">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={photo.previewUrl}
                    alt={`Photo ${photo.label || photo.file.name}`}
                    className="size-full object-cover"
                  />
                  {/* Status overlay */}
                  {photo.status === 'uploading' && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                      <Loader2 className="size-5 animate-spin text-white" />
                    </div>
                  )}
                  {photo.status === 'error' && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                      <AlertTriangle className={cn('size-5', statusText.warn)} />
                    </div>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <input
                    type="text"
                    value={photo.label}
                    onChange={(e) => handleLabelChange(photo.id, e.target.value)}
                    ref={(el) => { if (photo.status === 'staged' && !photo.serverPhotoId && el) el.focus() }}
                    placeholder="Label (optional)"
                    className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                  <p className="mt-1 text-xs text-muted-foreground truncate">{photo.file.name}</p>
                  {photo.status === 'error' && (
                    <>
                      {photo.errorMessage && (
                        <p className="mt-1 truncate text-[10px] text-muted-foreground">
                          {photo.errorMessage}
                        </p>
                      )}
                      <button
                        type="button"
                        onClick={() => retryUpload(photo.id)}
                        className={cn('mt-1 text-xs underline underline-offset-2', statusText.warn)}
                      >
                        Retry upload
                      </button>
                    </>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => removePhoto(photo.id)}
                  className="shrink-0 rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  <X className="size-4" />
                </button>
              </div>
              <div>
                <p className="mb-1.5 text-xs font-medium text-muted-foreground">Meal time</p>
                <MealTimeChips
                  value={photo.mealTime}
                  referenceDate={entryLocalDate(date)}
                  onChange={(d) => {
                    setPhotos((prev) =>
                      prev.map((p) => p.id === photo.id ? { ...p, mealTime: d } : p),
                    )
                  }}
                />
              </div>
              {((acceptedConnections.length > 0) || joinedGroups.length > 0) && (
                <TagPeoplePicker
                  mode="local"
                  connections={acceptedConnections}
                  groups={joinedGroups}
                  selectedHandles={photo.taggedHandles}
                  selectedGroupIds={photo.taggedGroupIds}
                  onChangeHandles={(taggedHandles) => {
                    setPhotos((prev) =>
                      prev.map((p) => p.id === photo.id ? { ...p, taggedHandles } : p),
                    )
                  }}
                  onChangeGroupIds={(taggedGroupIds) => {
                    setPhotos((prev) =>
                      prev.map((p) => p.id === photo.id ? { ...p, taggedGroupIds } : p),
                    )
                  }}
                />
              )}
            </div>
          ))}
        </div>
      )}

      <MealLibrarySheet
        open={libraryOpen}
        onOpenChange={setLibraryOpen}
        date={date}
        ensureEntryExists={ensureEntryExists}
        onEntryEnsured={onEntryEnsured}
      />
    </div>
  )
}
