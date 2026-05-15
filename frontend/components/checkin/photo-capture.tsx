'use client'

import { useRef } from 'react'
import { Camera, ImageIcon, X } from 'lucide-react'
import { MealTimeChips } from './meal-time-chips'

interface PhotoCaptureProps {
  photos: File[]
  labels: string[]
  mealTimes: (Date | null)[]
  onPhotosChange: (photos: File[]) => void
  onLabelsChange: (labels: string[]) => void
  onMealTimesChange: (mealTimes: (Date | null)[]) => void
}

export function PhotoCapture({
  photos,
  labels,
  mealTimes,
  onPhotosChange,
  onLabelsChange,
  onMealTimesChange,
}: PhotoCaptureProps) {
  const cameraRef = useRef<HTMLInputElement>(null)
  const galleryRef = useRef<HTMLInputElement>(null)

  const handleFileSelect = (files: FileList | null) => {
    if (!files) return
    const incoming = Array.from(files)
    const now = new Date()
    onPhotosChange([...photos, ...incoming])
    onLabelsChange([...labels, ...incoming.map(() => '')])
    onMealTimesChange([...mealTimes, ...incoming.map(() => new Date(now))])
  }

  const removePhoto = (index: number) => {
    onPhotosChange(photos.filter((_, i) => i !== index))
    onLabelsChange(labels.filter((_, i) => i !== index))
    onMealTimesChange(mealTimes.filter((_, i) => i !== index))
  }

  const updateLabel = (index: number, label: string) => {
    const next = [...labels]
    next[index] = label
    onLabelsChange(next)
  }

  const updateMealTime = (index: number, d: Date) => {
    const next = [...mealTimes]
    next[index] = d
    onMealTimesChange(next)
  }

  return (
    <div className="space-y-3">
      <label className="text-sm font-medium leading-none">Photos</label>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => cameraRef.current?.click()}
          className="flex min-h-[44px] flex-1 items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium transition-colors hover:bg-muted"
        >
          <Camera className="size-4" />
          Take Photo
        </button>
        <button
          type="button"
          onClick={() => galleryRef.current?.click()}
          className="flex min-h-[44px] flex-1 items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium transition-colors hover:bg-muted"
        >
          <ImageIcon className="size-4" />
          Choose Photo
        </button>
      </div>

      <input
        ref={cameraRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={(e) => handleFileSelect(e.target.files)}
        className="hidden"
      />
      <input
        ref={galleryRef}
        type="file"
        accept="image/*"
        onChange={(e) => handleFileSelect(e.target.files)}
        className="hidden"
      />

      {photos.length > 0 && (
        <div className="space-y-3">
          {photos.map((photo, index) => (
            <div key={index} className="rounded-lg border border-border p-3 space-y-2">
              <div className="flex items-start gap-3">
                <div className="relative size-16 shrink-0 overflow-hidden rounded-md bg-muted">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={URL.createObjectURL(photo)}
                    alt={`Photo ${index + 1}`}
                    className="size-full object-cover"
                  />
                </div>
                <div className="flex-1">
                  <input
                    type="text"
                    value={labels[index] || ''}
                    onChange={(e) => updateLabel(index, e.target.value)}
                    placeholder="Label (optional)"
                    className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                  <p className="mt-1 text-xs text-muted-foreground">{photo.name}</p>
                </div>
                <button
                  type="button"
                  onClick={() => removePhoto(index)}
                  className="shrink-0 rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  <X className="size-4" />
                </button>
              </div>
              <div>
                <p className="mb-1.5 text-xs font-medium text-muted-foreground">Meal time</p>
                <MealTimeChips
                  value={mealTimes[index] ?? null}
                  onChange={(d) => updateMealTime(index, d)}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
