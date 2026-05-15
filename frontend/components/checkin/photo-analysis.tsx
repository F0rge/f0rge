'use client'

import { useState } from 'react'
import { Loader2, X, RefreshCw, Check } from 'lucide-react'
import {
  usePhotoAnalysis,
  useConfirmAnalysis,
  useRetryAnalysis,
  useDeleteIngredient,
  useUpdateIngredient,
} from '@/lib/api/hooks'
import { IngredientEditor } from './ingredient-editor'
import type { PhotoIngredient } from '@/lib/api/types'

interface PhotoAnalysisProps {
  photoId: number
}

function DietaryBadges({ ingredient }: { ingredient: PhotoIngredient }) {
  const badges: { label: string; className: string }[] = []

  // Histamine score
  if (ingredient.histamine_score !== null) {
    const hColors: Record<number, string> = {
      0: 'bg-green-100 text-green-800',
      1: 'bg-yellow-100 text-yellow-800',
      2: 'bg-orange-100 text-orange-800',
      3: 'bg-red-100 text-red-800',
    }
    badges.push({
      label: `H:${ingredient.histamine_score}`,
      className: hColors[ingredient.histamine_score] ?? 'bg-gray-100 text-gray-600',
    })
  }

  // Gluten
  if (ingredient.contains_gluten) {
    badges.push({ label: 'Gluten', className: 'bg-red-100 text-red-800' })
  }

  // Dairy
  if (ingredient.contains_dairy) {
    badges.push({ label: 'Dairy', className: 'bg-blue-100 text-blue-800' })
  }

  // FODMAP flags. For each category, `high` takes precedence over
  // `moderate`. High = orange badge; moderate = softer amber badge with a
  // `?` suffix so high vs moderate is also distinguishable in screenshots
  // and copied text. See issue #14.
  const FODMAP_HIGH = 'bg-orange-100 text-orange-800'
  const FODMAP_MOD = 'bg-amber-100 text-amber-800'
  const fodmapCategories: Array<{
    value: string | null
    abbrev: string
  }> = [
    { value: ingredient.fodmap_oligos, abbrev: 'F:O' },
    { value: ingredient.fodmap_fructose, abbrev: 'F:Fr' },
    { value: ingredient.fodmap_polyols, abbrev: 'F:P' },
    { value: ingredient.fodmap_lactose, abbrev: 'F:L' },
  ]
  for (const { value, abbrev } of fodmapCategories) {
    if (value === 'high') {
      badges.push({ label: abbrev, className: FODMAP_HIGH })
    } else if (value === 'moderate') {
      badges.push({ label: `${abbrev}?`, className: FODMAP_MOD })
    }
  }

  // If nothing is known at all, show unknown
  if (
    badges.length === 0 &&
    ingredient.histamine_score === null &&
    ingredient.contains_gluten === null &&
    ingredient.contains_dairy === null
  ) {
    badges.push({ label: '?', className: 'bg-gray-100 text-gray-500' })
  }

  return (
    <span className="inline-flex flex-wrap gap-0.5">
      {badges.map((b, i) => (
        <span
          key={i}
          className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-none ${b.className}`}
        >
          {b.label}
        </span>
      ))}
    </span>
  )
}

function IngredientRow({
  ingredient,
  canEdit,
}: {
  ingredient: PhotoIngredient
  canEdit: boolean
}) {
  const deleteIngredient = useDeleteIngredient()
  const updateIngredient = useUpdateIngredient()
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(ingredient.name)

  const startEdit = () => {
    setDraft(ingredient.name)
    setEditing(true)
  }

  const cancelEdit = () => {
    setEditing(false)
    setDraft(ingredient.name)
  }

  const saveEdit = async () => {
    if (updateIngredient.isPending) return
    const trimmed = draft.trim()
    if (!trimmed || trimmed === ingredient.name) {
      cancelEdit()
      return
    }
    try {
      await updateIngredient.mutateAsync({
        ingredientId: ingredient.id,
        data: { name: trimmed },
      })
      setEditing(false)
    } catch {
      // Error handled by React Query; keep input open so user can retry
    }
  }

  if (editing && canEdit) {
    return (
      <div className="flex items-center gap-1.5 py-0.5">
        <input
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              saveEdit()
            } else if (e.key === 'Escape') {
              e.preventDefault()
              cancelEdit()
            }
          }}
          onBlur={saveEdit}
          disabled={updateIngredient.isPending}
          autoFocus
          aria-label="Edit ingredient name"
          className="h-6 flex-1 rounded border border-border bg-background px-1.5 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
        />
        {updateIngredient.isPending && (
          <Loader2 className="size-3 animate-spin text-muted-foreground" />
        )}
      </div>
    )
  }

  return (
    <div className="flex items-center gap-1.5 py-0.5">
      {canEdit ? (
        <button
          type="button"
          onClick={startEdit}
          className="text-left text-xs text-foreground hover:underline"
          aria-label={`Edit ingredient ${ingredient.name}`}
        >
          {ingredient.name}
        </button>
      ) : (
        <span className="text-xs text-foreground">{ingredient.name}</span>
      )}
      <DietaryBadges ingredient={ingredient} />
      {canEdit && (
        <button
          type="button"
          onClick={() => deleteIngredient.mutate(ingredient.id)}
          className="ml-auto shrink-0 rounded p-0.5 text-muted-foreground hover:text-foreground transition-colors"
          aria-label={`Remove ingredient ${ingredient.name}`}
        >
          <X className="size-3" />
        </button>
      )}
    </div>
  )
}

export function PhotoAnalysis({ photoId }: PhotoAnalysisProps) {
  const { data: analysis, isLoading } = usePhotoAnalysis(photoId)
  const confirmAnalysis = useConfirmAnalysis()
  const retryAnalysis = useRetryAnalysis()

  // No analysis exists yet
  if (isLoading) {
    return null
  }

  if (!analysis) {
    return null
  }

  // Pending / Analyzing
  if (analysis.status === 'pending' || analysis.status === 'analyzing') {
    return (
      <div className="mt-2 rounded-lg border border-border p-2.5">
        <div className="flex items-center gap-2">
          <Loader2 className="size-3.5 animate-spin text-muted-foreground" />
          <span className="text-xs text-muted-foreground">Analyzing...</span>
        </div>
        <div className="mt-2 space-y-1.5">
          <div className="h-3 w-2/3 animate-pulse rounded bg-muted" />
          <div className="h-3 w-1/2 animate-pulse rounded bg-muted" />
          <div className="h-3 w-3/5 animate-pulse rounded bg-muted" />
        </div>
      </div>
    )
  }

  // Failed
  if (analysis.status === 'failed') {
    return (
      <div className="mt-2 rounded-lg border border-border p-2.5">
        <p className="text-xs text-muted-foreground">
          {analysis.error_message || 'Analysis failed'}
        </p>
        <button
          type="button"
          onClick={() => retryAnalysis.mutate(photoId)}
          disabled={retryAnalysis.isPending}
          className="mt-1.5 flex items-center gap-1 text-xs font-medium text-primary hover:text-primary/80 transition-colors disabled:opacity-50"
        >
          <RefreshCw className="size-3" />
          Retry
        </button>
      </div>
    )
  }

  // Complete or Confirmed
  const isConfirmed = analysis.status === 'confirmed'
  const visibleIngredients = analysis.ingredients.filter((ing) => ing.visible)

  return (
    <div className="mt-2 rounded-lg border border-border p-2.5">
      {/* Dish header */}
      {analysis.dish_name && (
        <div className="flex items-center gap-1.5">
          <span className="text-sm font-semibold text-foreground">{analysis.dish_name}</span>
          {analysis.dish_confidence !== null && (
            <span className="text-xs text-muted-foreground">
              ({Math.round(analysis.dish_confidence * 100)}%)
            </span>
          )}
          {isConfirmed && (
            <Check className="ml-auto size-3.5 text-green-600" />
          )}
        </div>
      )}

      {/* Ingredients */}
      {visibleIngredients.length > 0 && (
        <div className="mt-1.5 space-y-0.5">
          {visibleIngredients.map((ing) => (
            <IngredientRow key={ing.id} ingredient={ing} canEdit={!isConfirmed} />
          ))}
        </div>
      )}

      {/* Add ingredient + confirm (only when not confirmed) */}
      {!isConfirmed && (
        <div className="mt-2 flex items-center justify-between gap-2">
          <IngredientEditor photoId={photoId} onAdded={() => {}} />
          <button
            type="button"
            onClick={() => confirmAnalysis.mutate(photoId)}
            disabled={confirmAnalysis.isPending}
            className="flex items-center gap-1 rounded-md bg-green-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-green-700 transition-colors disabled:opacity-50"
          >
            <Check className="size-3" />
            Confirm
          </button>
        </div>
      )}
    </div>
  )
}
