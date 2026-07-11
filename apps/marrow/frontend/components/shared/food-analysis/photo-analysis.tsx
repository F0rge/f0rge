'use client'

import { useState } from 'react'
import { Loader2, X, RefreshCw, Check } from 'lucide-react'
import {
  usePhotoAnalysis,
  useConfirmAnalysis,
  useRetryAnalysis,
  useDeleteIngredient,
  useUpdateIngredient,
  useUpdateDietaryConfirm,
} from '@/lib/api/hooks'
import { handleMutationError } from '@f0rge/ui/api'
import { IngredientEditor } from './ingredient-editor'
import { DietaryBadges } from './dietary-badges'
import type { PhotoIngredient } from '@/lib/api/types'

type PhotoAnalysisMode = 'view' | 'edit'

interface PhotoAnalysisProps {
  photoId: number
  mode?: PhotoAnalysisMode
  hideConfirmButton?: boolean
  /** Hide the dish-name/confidence header row — used by PhotoFocusOverlay,
   * which already shows the title in its own header. */
  hideTitle?: boolean
}

function IngredientRow({
  ingredient,
  canEdit,
  glutenFreeConfirmed,
  lactoseFreeConfirmed,
}: {
  ingredient: PhotoIngredient
  canEdit: boolean
  glutenFreeConfirmed: boolean
  lactoseFreeConfirmed: boolean
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
    } catch (err) {
      // Keep the input open on failure so the user can retry or cancel.
      handleMutationError(err, 'Failed to update ingredient')
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
          className="min-h-[44px] flex-1 rounded border border-border bg-background px-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
        />
        {updateIngredient.isPending && (
          <Loader2 className="size-4 animate-spin text-muted-foreground" />
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
          className="min-h-[44px] flex-1 text-left text-sm text-foreground hover:underline"
          aria-label={`Edit ingredient ${ingredient.name}`}
        >
          {ingredient.name}
        </button>
      ) : (
        <span className="text-sm text-foreground">{ingredient.name}</span>
      )}
      <DietaryBadges
        ingredient={ingredient}
        glutenFreeConfirmed={glutenFreeConfirmed}
        lactoseFreeConfirmed={lactoseFreeConfirmed}
      />
      {canEdit && (
        <button
          type="button"
          onClick={() => deleteIngredient.mutate(ingredient.id)}
          className="ml-auto flex min-h-[44px] min-w-[44px] shrink-0 items-center justify-center rounded text-muted-foreground hover:text-foreground transition-colors"
          aria-label={`Remove ingredient ${ingredient.name}`}
        >
          <X className="size-4" />
        </button>
      )}
    </div>
  )
}

export function PhotoAnalysis({
  photoId,
  mode = 'edit',
  hideConfirmButton = false,
  hideTitle = false,
}: PhotoAnalysisProps) {
  const { data: analysis, isLoading } = usePhotoAnalysis(photoId)
  const confirmAnalysis = useConfirmAnalysis()
  const retryAnalysis = useRetryAnalysis()
  const updateDietaryConfirm = useUpdateDietaryConfirm()

  const canEdit = mode === 'edit'

  if (isLoading) {
    return null
  }

  if (!analysis) {
    return null
  }

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

  const isConfirmed = analysis.status === 'confirmed'
  const needsReview = analysis.status === 'needs_review'
  const visibleIngredients = analysis.ingredients.filter((ing) => ing.visible)
  const inferredIngredients = analysis.ingredients.filter((ing) => !ing.visible)

  // In the original check-in flow (mode='edit'), edit affordances were gated
  // behind !isConfirmed. Now canEdit is derived solely from mode, so the
  // history page can unlock editing on confirmed analyses without a status change.
  const showEditAffordances = canEdit

  return (
    <div className="mt-2 rounded-lg border border-border p-2.5">
      {needsReview && (
        <p className="mb-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-1.5 text-xs text-amber-900">
          Low confidence — review ingredients before confirming.
        </p>
      )}

      {!hideTitle && analysis.dish_name && (
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

      {showEditAffordances && (
        <div className="mt-2 grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() =>
              updateDietaryConfirm.mutate({
                photoId,
                gluten_free_confirmed: !analysis.gluten_free_confirmed,
              })
            }
            disabled={updateDietaryConfirm.isPending}
            aria-pressed={analysis.gluten_free_confirmed}
            className={[
              'min-h-[48px] rounded-xl border px-2 py-2.5 text-sm font-medium transition-all disabled:opacity-50',
              analysis.gluten_free_confirmed
                ? 'border-primary bg-primary text-primary-foreground shadow-sm'
                : 'border-border bg-background text-muted-foreground',
            ].join(' ')}
          >
            Gluten-free
          </button>
          <button
            type="button"
            onClick={() =>
              updateDietaryConfirm.mutate({
                photoId,
                lactose_free_confirmed: !analysis.lactose_free_confirmed,
              })
            }
            disabled={updateDietaryConfirm.isPending}
            aria-pressed={analysis.lactose_free_confirmed}
            className={[
              'min-h-[48px] rounded-xl border px-2 py-2.5 text-sm font-medium transition-all disabled:opacity-50',
              analysis.lactose_free_confirmed
                ? 'border-primary bg-primary text-primary-foreground shadow-sm'
                : 'border-border bg-background text-muted-foreground',
            ].join(' ')}
          >
            Lactose-free
          </button>
        </div>
      )}

      {visibleIngredients.length > 0 && (
        <div className="mt-1.5 space-y-0.5">
          {visibleIngredients.map((ing) => (
            <IngredientRow
              key={ing.id}
              ingredient={ing}
              canEdit={showEditAffordances}
              glutenFreeConfirmed={analysis.gluten_free_confirmed}
              lactoseFreeConfirmed={analysis.lactose_free_confirmed}
            />
          ))}
        </div>
      )}

      {inferredIngredients.length > 0 && (
        <div className="mt-2 border-t border-dashed border-border pt-1.5">
          <div className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">
            Inferred (counted but not visible in photo)
          </div>
          <div className="space-y-0.5 opacity-70">
            {inferredIngredients.map((ing) => (
              <IngredientRow
                key={ing.id}
                ingredient={ing}
                canEdit={showEditAffordances}
                glutenFreeConfirmed={analysis.gluten_free_confirmed}
                lactoseFreeConfirmed={analysis.lactose_free_confirmed}
              />
            ))}
          </div>
        </div>
      )}

      {showEditAffordances && (
        <div className="mt-2 space-y-2">
          <IngredientEditor
            photoId={photoId}
            existingNames={analysis.ingredients.map((ing) => ing.name)}
            onAdded={() => {}}
          />
          {!hideConfirmButton && !isConfirmed && (
            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => confirmAnalysis.mutate(photoId)}
                disabled={confirmAnalysis.isPending}
                className="flex min-h-[44px] items-center gap-1.5 rounded-md bg-green-600 px-4 text-sm font-medium text-white hover:bg-green-700 transition-colors disabled:opacity-50"
              >
                <Check className="size-4" />
                Confirm
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
