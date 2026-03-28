'use client'

import { useRef } from 'react'
import { Camera, ImageIcon, X } from 'lucide-react'

interface PhotoCaptureProps {
  photos: File[]
  labels: string[]
  onPhotosChange: (photos: File[]) => void
  onLabelsChange: (labels: string[]) => void
}

export function PhotoCapture({ photos, labels, onPhotosChange, onLabelsChange }: PhotoCaptureProps) {
  const cameraRef = useRef<HTMLInputElement>(null)
  const galleryRef = useRef<HTMLInputElement>(null)

  const handleFileSelect = (files: FileList | null) => {
    if (!files) return
    const newPhotos = [...photos, ...Array.from(files)]
    const newLabels = [...labels, ...Array.from(files).map(() => '')]
    onPhotosChange(newPhotos)
    onLabelsChange(newLabels)
  }

  const removePhoto = (index: number) => {
    const newPhotos = photos.filter((_, i) => i !== index)
    const newLabels = labels.filter((_, i) => i !== index)
    onPhotosChange(newPhotos)
    onLabelsChange(newLabels)
  }

  const updateLabel = (index: number, label: string) => {
    const newLabels = [...labels]
    newLabels[index] = label
    onLabelsChange(newLabels)
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
            <div key={index} className="flex items-start gap-3 rounded-lg border border-border p-3">
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
          ))}
        </div>
      )}
    </div>
  )
}
