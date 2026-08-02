'use client'

import { useRef, useState, useCallback } from 'react'
import { BookOpen, Camera, ImageIcon, X, Loader2, AlertTriangle } from 'lucide-react'
import { MealLibrarySheet } from './meal-library-sheet'
import { MealTimeChips } from './meal-time-chips'
import { TagPeoplePicker } from './tag-people-picker'
import { useUploadPhoto } from '@/lib/api/hooks'
import { useConnections, useGroups } from '@/lib/api/hooks/social'
import { getErrorDetail } from '@f0rge/ui/api'

interface StagedPhoto {
  id: string
  file: File
  label: string
  mealTime: Date
  taggedHandles: string[]
  taggedGroupIds: string[]
  status: 'staged' | 'uploading' | 'error'
  errorMessage?: string
}

interface PhotoCaptureProps {
  date: string
  ensureEntryExists: () => Promise<void>
  onEntryEnsured?: () => void
}

function generateId(): string {
  return Math.random().toString(36).slice(2)
}

export function PhotoCapture({ date, ensureEntryExists, onEntryEnsured }: PhotoCaptureProps) {
  const cameraRef = useRef<HTMLInputElement>(null)
  const galleryRef = useRef<HTMLInputElement>(null)
  const uploadPhoto = useUploadPhoto()
  const connections = useConnections()
  const groups = useGroups()
  const acceptedConnections = connections.data?.accepted ?? []
  const joinedGroups = (groups.data ?? []).filter((g) => g.my_status === 'joined')

  const [photos, setPhotos] = useState<StagedPhoto[]>([])
  const [libraryOpen, setLibraryOpen] = useState(false)

  const handleFileSelect = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return
    const incoming = Array.from(files)
    const now = new Date()

    // Stage all files so the UI shows them immediately. Upload is triggered
    // manually after the user sets the label and meal time.
    const staged: StagedPhoto[] = incoming.map((file) => ({
      id: generateId(),
      file,
      label: '',
      mealTime: new Date(now),
      taggedHandles: [],
      taggedGroupIds: [],
      status: 'staged',
    }))
    setPhotos((prev) => [...prev, ...staged])
  }, [])

  const removePhoto = useCallback((id: string) => {
    setPhotos((prev) => prev.filter((p) => p.id !== id))
  }, [])

  const retryUpload = useCallback(async (id: string) => {
    const photo = photos.find((p) => p.id === id)
    if (!photo) return

    setPhotos((prev) =>
      prev.map((p) => p.id === id ? { ...p, status: 'uploading', errorMessage: undefined } : p),
    )

    await ensureEntryExists()
    onEntryEnsured?.()

    try {
      await uploadPhoto.mutateAsync({
        date,
        file: photo.file,
        label: photo.label || undefined,
        mealTime: photo.mealTime,
        taggedHandles: photo.taggedHandles,
        taggedGroupIds: photo.taggedGroupIds,
      })

      setPhotos((prev) => prev.filter((p) => p.id !== id))
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
  }, [photos, date, ensureEntryExists, onEntryEnsured, uploadPhoto])

  const triggerUpload = useCallback(async (id: string) => {
    const photo = photos.find((p) => p.id === id)
    if (!photo || photo.status !== 'staged') return

    setPhotos((prev) =>
      prev.map((p) => p.id === id ? { ...p, status: 'uploading', errorMessage: undefined } : p),
    )

    await ensureEntryExists()
    onEntryEnsured?.()

    try {
      await uploadPhoto.mutateAsync({
        date,
        file: photo.file,
        label: photo.label || undefined,
        mealTime: photo.mealTime,
        taggedHandles: photo.taggedHandles,
        taggedGroupIds: photo.taggedGroupIds,
      })

      setPhotos((prev) => prev.filter((p) => p.id !== id))
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
  }, [photos, date, ensureEntryExists, onEntryEnsured, uploadPhoto])

  return (
    <div className="space-y-3">
      <label className="text-sm font-medium leading-none">Add meal</label>

      <div className="grid grid-cols-3 gap-2">
        <button
          type="button"
          onClick={() => cameraRef.current?.click()}
          className="flex min-h-[44px] flex-col items-center justify-center gap-1 rounded-lg border border-border bg-background px-2 py-2 text-xs font-medium transition-colors hover:bg-muted sm:text-sm sm:flex-row sm:gap-2"
        >
          <Camera className="size-4 shrink-0" />
          Take Photo
        </button>
        <button
          type="button"
          onClick={() => galleryRef.current?.click()}
          className="flex min-h-[44px] flex-col items-center justify-center gap-1 rounded-lg border border-border bg-background px-2 py-2 text-xs font-medium transition-colors hover:bg-muted sm:text-sm sm:flex-row sm:gap-2"
        >
          <ImageIcon className="size-4 shrink-0" />
          Choose Photo
        </button>
        <button
          type="button"
          onClick={() => setLibraryOpen(true)}
          className="flex min-h-[44px] flex-col items-center justify-center gap-1 rounded-lg border border-border bg-background px-2 py-2 text-xs font-medium transition-colors hover:bg-muted sm:text-sm sm:flex-row sm:gap-2"
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
          {photos.map((photo) => (
            <div key={photo.id} className="rounded-lg border border-border p-3 space-y-2">
              <div className="flex items-start gap-3">
                <div className="relative size-16 shrink-0 overflow-hidden rounded-md bg-muted">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={URL.createObjectURL(photo.file)}
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
                      <AlertTriangle className="size-5 text-amber-400" />
                    </div>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <input
                    type="text"
                    value={photo.label}
                    onChange={(e) => {
                      const label = e.target.value
                      setPhotos((prev) =>
                        prev.map((p) => p.id === photo.id ? { ...p, label } : p),
                      )
                    }}
                    disabled={photo.status === 'uploading'}
                    ref={(el) => { if (photo.status === 'staged' && el) el.focus() }}
                    placeholder="Label (optional)"
                    className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
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
                        onClick={() => void retryUpload(photo.id)}
                        className="mt-1 text-xs text-amber-600 underline underline-offset-2 dark:text-amber-400"
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
              {photo.status === 'staged' && (
                <button
                  type="button"
                  onClick={() => void triggerUpload(photo.id)}
                  className="mt-2 flex min-h-[36px] w-full items-center justify-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                >
                  Upload
                </button>
              )}
              <div>
                <p className="mb-1.5 text-xs font-medium text-muted-foreground">Meal time</p>
                <MealTimeChips
                  value={photo.mealTime}
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
                  disabled={photo.status === 'uploading'}
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
