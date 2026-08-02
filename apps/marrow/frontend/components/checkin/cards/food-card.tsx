'use client'

import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Card, CardContent } from '@f0rge/ui'
import { PhotoCapture } from '@/components/checkin/photo-capture'
import { RecentMealsStrip } from '@/components/checkin/recent-meals-strip'
import type { Entry } from '@/lib/api/types'
import { useDeletePhoto, useDietTagCatalog } from '@/lib/api/hooks'
import { handleMutationError } from '@f0rge/ui/api'
import { CheckinCardHeader } from '@/components/checkin/checkin-card-header'
import type { CheckinCardCollapseProps } from '@/components/checkin/checkin-card-collapse'
import { DietRiskSection } from './food/diet-risk-section'
import { MealCard } from './food/meal-card'

interface FoodCardProps extends CheckinCardCollapseProps {
  date: string
  existingEntry?: Entry | null
  existingPhotos: Entry['photos']
  dietRisk: string
  onDietToggle: (id: string) => void
  onPhotosChange: (photos: Entry['photos']) => void
  ensureEntryExists: () => Promise<void>
  onEntryEnsured: () => void
  onOpenPhotoFocus: (photoId: number) => void
}

export function FoodCard({
  date,
  existingEntry,
  existingPhotos,
  dietRisk,
  onDietToggle,
  onPhotosChange,
  ensureEntryExists,
  onEntryEnsured,
  onOpenPhotoFocus,
  collapsed,
  onToggleCollapsed,
}: FoodCardProps) {
  const deletePhotoMutation = useDeletePhoto()
  const queryClient = useQueryClient()
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const { data: dietCatalog = [], isLoading: dietCatalogLoading } = useDietTagCatalog(false)

  const handleDeletePhoto = async (photoId: number) => {
    setDeletingId(photoId)
    try {
      await deletePhotoMutation.mutateAsync(photoId)
      onPhotosChange(existingPhotos.filter((p) => p.id !== photoId))
      queryClient.invalidateQueries({ queryKey: ['entry', date] })
      toast.success('Photo deleted')
    } catch (err) {
      handleMutationError(err, 'Failed to delete photo')
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <Card className="h-full">
      <CheckinCardHeader
        title="Food & drinks"
        tier="core"
        collapsed={collapsed}
        onToggleCollapsed={onToggleCollapsed}
      />
      {!collapsed && (
      <CardContent className="space-y-6">
        <DietRiskSection
          existingEntry={existingEntry}
          existingPhotos={existingPhotos}
          dietRisk={dietRisk}
          onToggle={onDietToggle}
          catalog={dietCatalog}
          catalogLoading={dietCatalogLoading}
        />

        {existingPhotos.length > 0 && (
          <div className="space-y-3">
            <label className="text-sm font-semibold">Today&apos;s meals</label>
            <div className="grid grid-cols-2 gap-3">
              {existingPhotos.map((photo) => (
                <MealCard
                  key={photo.id}
                  photo={photo}
                  onOpen={onOpenPhotoFocus}
                  onDelete={handleDeletePhoto}
                  deleting={deletingId === photo.id}
                />
              ))}
            </div>
          </div>
        )}

        <RecentMealsStrip date={date} />

        <PhotoCapture
          date={date}
          ensureEntryExists={ensureEntryExists}
          onEntryEnsured={onEntryEnsured}
        />
      </CardContent>
      )}
    </Card>
  )
}
