'use client'

import { useEffect, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'
import { Eye, EyeOff, Pencil } from 'lucide-react'
import { Dialog, DialogContent } from '@f0rge/ui'
import { MealCompanionsSection } from '@/components/checkin/meal-companions-section'
import { MealIconThumb, photoHasImage } from '@/components/checkin/meal-icon-thumb'
import { MealTimeChips } from '@/components/checkin/meal-time-chips'
import {
  usePhotoAnalysis,
  useUpdatePhotoLabel,
  useUpdatePhotoMealTime,
  useUpdatePhotoVisibility,
} from '@/lib/api/hooks'
import { handleMutationError } from '@f0rge/ui/api'
import { PhotoAnalysis } from './photo-analysis'
import { PhotoDietTagsSection } from './photo-diet-tags-section'
import type { Photo } from '@/lib/api/types'

// ---------------------------------------------------------------------------
// useReducedMotion — duplicated from components/checkin/floating-status-capsule.tsx
// on purpose (see frontend-dev memory: not worth extracting a shared file for
// 12 lines used in two places).
// ---------------------------------------------------------------------------

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  })
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const handler = (e: MediaQueryListEvent) => setReduced(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])
  return reduced
}

// ---------------------------------------------------------------------------
// useSheetGestures — pointer-driven swipe (switch photo) + drag-down-to-close
// for the bottom sheet. Native pointer events, axis-locked after ~10px of
// movement, no touch-event soup.
// ---------------------------------------------------------------------------

const AXIS_LOCK_PX = 10
const HORIZONTAL_DISMISS_PX = 60
const HORIZONTAL_FLICK_PX_MS = 0.4
const VERTICAL_DISMISS_PX = 100
const VERTICAL_FLICK_PX_MS = 0.5

interface SheetGestureOptions {
  photoId: number | null
  photos: Photo[]
  onSelectPhoto: (id: number) => void
  onClose: () => void
  reducedMotion: boolean
  /** Ref to the scrollable ingredient list — dismiss is allowed when it's
   * scrolled to the top, in addition to drags starting in the top region. */
  scrollRef: React.RefObject<HTMLDivElement | null>
}

interface SheetGestureState {
  dragY: number
  phase: 'idle' | 'dragging' | 'settling'
}

function useSheetGestures({
  photoId,
  photos,
  onSelectPhoto,
  onClose,
  reducedMotion,
  scrollRef,
}: SheetGestureOptions) {
  const [state, setState] = useState<SheetGestureState>({ dragY: 0, phase: 'idle' })

  const axisRef = useRef<'x' | 'y' | null>(null)
  const startRef = useRef({ x: 0, y: 0, t: 0 })
  const canDismissRef = useRef(false)
  const capturedRef = useRef(false)

  const onPointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (e.pointerType === 'mouse') return // desktop centered modal: no-op

    axisRef.current = null
    capturedRef.current = false
    startRef.current = { x: e.clientX, y: e.clientY, t: e.timeStamp }

    const target = e.target as HTMLElement
    const startedInTopRegion = target.closest('[data-sheet-top-region]') !== null
    const scrollerAtTop = (scrollRef.current?.scrollTop ?? 0) <= 0
    canDismissRef.current = startedInTopRegion || scrollerAtTop
  }

  const onPointerMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (e.pointerType === 'mouse') return
    if (axisRef.current === null) {
      const dx = e.clientX - startRef.current.x
      const dy = e.clientY - startRef.current.y
      if (Math.abs(dx) < AXIS_LOCK_PX && Math.abs(dy) < AXIS_LOCK_PX) return

      axisRef.current = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y'
      if (axisRef.current === 'y' && !canDismissRef.current) {
        // Vertical movement mid-list must scroll, not drag the sheet.
        axisRef.current = null
        return
      }
      if (!capturedRef.current) {
        e.currentTarget.setPointerCapture(e.pointerId)
        capturedRef.current = true
      }
    }

    if (axisRef.current === 'y') {
      const dy = Math.max(0, e.clientY - startRef.current.y)
      setState({ dragY: dy, phase: 'dragging' })
    }
  }

  const finishVertical = (e: ReactPointerEvent<HTMLDivElement>) => {
    const dy = Math.max(0, e.clientY - startRef.current.y)
    const dt = Math.max(1, e.timeStamp - startRef.current.t)
    const velocity = dy / dt
    const shouldDismiss = dy > VERTICAL_DISMISS_PX || velocity > VERTICAL_FLICK_PX_MS
    if (shouldDismiss) {
      if (reducedMotion) {
        onClose()
        setState({ dragY: 0, phase: 'idle' })
        return
      }
      // Animate the rest of the way out ourselves (transition turns on via
      // 'settling'), then close and reset so a reopen isn't offset/faded —
      // this component never unmounts, so stale dragY/phase would otherwise
      // persist across dismiss/reopen.
      const h = window.innerHeight
      setState({ dragY: h, phase: 'settling' })
      window.setTimeout(() => {
        onClose()
        setState({ dragY: 0, phase: 'idle' })
      }, 260)
    } else {
      setState({ dragY: 0, phase: 'settling' })
    }
  }

  const finishHorizontal = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (photoId === null || photos.length <= 1) return
    const dx = e.clientX - startRef.current.x
    const dt = Math.max(1, e.timeStamp - startRef.current.t)
    const velocity = Math.abs(dx) / dt
    const past = Math.abs(dx) > HORIZONTAL_DISMISS_PX || velocity > HORIZONTAL_FLICK_PX_MS
    if (!past) return

    const index = photos.findIndex((p) => p.id === photoId)
    if (index === -1) return
    // Swipe left → next photo, swipe right → previous. Clamp at the ends.
    const nextIndex = dx < 0 ? index + 1 : index - 1
    if (nextIndex < 0 || nextIndex >= photos.length) return
    onSelectPhoto(photos[nextIndex].id)
  }

  const onPointerUp = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (e.pointerType === 'mouse') return
    if (axisRef.current === 'y') finishVertical(e)
    else if (axisRef.current === 'x') finishHorizontal(e)
    axisRef.current = null
  }

  const onPointerCancel = () => {
    if (axisRef.current === 'y') setState({ dragY: 0, phase: 'settling' })
    axisRef.current = null
  }

  const { dragY, phase } = state
  const opacity = dragY > 0 ? Math.max(0.4, 1 - dragY / 400) : 1
  const style: React.CSSProperties = {
    transform: dragY > 0 ? `translateY(${dragY}px)` : undefined,
    opacity: dragY > 0 ? opacity : undefined,
    transition: reducedMotion ? 'none' : phase === 'settling' ? 'transform 0.25s ease-out, opacity 0.25s ease-out' : 'none',
    // pan-y let the UA claim the vertical axis at drag-lock and fire
    // pointercancel, snapping the sheet back before it reached the dismiss
    // threshold. `none` keeps the vertical drag ours. touch-action is not
    // inherited, so the scrollable ingredient list below keeps its default
    // `auto` and native touch-scroll there is unaffected (data-sheet-scroll).
    touchAction: 'none',
  }

  return {
    style,
    handlers: { onPointerDown, onPointerMove, onPointerUp, onPointerCancel },
  }
}

interface PhotoFocusOverlayProps {
  /** ID of the photo currently in focus. `null` means the overlay is closed. */
  photoId: number | null
  /** All photos for the entry, used for the meal-tab switcher when there are ≥2. */
  photos: Photo[]
  /** Whether the underlying form is in edit mode. Mirrors `PhotoAnalysis` mode. */
  mode?: 'view' | 'edit'
  /** Called when the user closes the overlay (X, Done, Esc, or backdrop). */
  onClose: () => void
  /** Called when the user switches to another photo via the tab row. */
  onSelectPhoto: (id: number) => void
}

interface TitleEditorProps {
  photoId: number
  label: string | null
  dishName: string | null
}

/** Entry calendar day encoded in photo filenames: `{YYYY-MM-DD}_photo-N.jpg`. */
function entryDateFromFilename(filename: string): Date | null {
  const match = /^(\d{4}-\d{2}-\d{2})_photo-/.exec(filename)
  if (!match) return null
  return new Date(`${match[1]}T00:00:00`)
}

/** Optimistic meal-time chips; remount via key={photoId} to reset without setState-in-effect. */
function MealTimeEditor({
  photoId,
  mealTime,
  filename,
}: {
  photoId: number
  mealTime: string | null
  filename: string | null
}) {
  const updateMealTime = useUpdatePhotoMealTime()
  const [optimisticMealTime, setOptimisticMealTime] = useState<string | null>(mealTime)

  const handleChange = async (d: Date) => {
    const iso = d.toISOString()
    setOptimisticMealTime(iso)
    try {
      await updateMealTime.mutateAsync({ photoId, mealTime: iso })
    } catch (err) {
      setOptimisticMealTime(mealTime)
      handleMutationError(err, 'Failed to update meal time')
    }
  }

  const chipValue = optimisticMealTime ? new Date(optimisticMealTime) : null
  const referenceDate =
    (filename ? entryDateFromFilename(filename) : null) ??
    (mealTime ? new Date(mealTime) : new Date())

  return (
    <div className="mb-3">
      <p className="mb-1.5 text-xs font-medium text-muted-foreground">Meal time</p>
      <MealTimeChips value={chipValue} onChange={handleChange} referenceDate={referenceDate} />
    </div>
  )
}

/**
 * Editable header title. Click the title or the pencil icon to reveal an
 * inline text input; Enter or blur commits via PATCH /photos/{id}. Clearing
 * the input (empty string) falls back to the AI dish_name. When the label is
 * empty and a dish_name exists, a small "AI: {dish_name} — Use" affordance
 * fills the input from the AI guess.
 */
function TitleEditor({ photoId, label, dishName }: TitleEditorProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(label ?? '')
  const updateLabel = useUpdatePhotoLabel()

  const title = label?.trim() || dishName || 'Photo'

  const commit = async (value: string) => {
    const trimmed = value.trim()
    if (trimmed === (label ?? '').trim()) {
      setEditing(false)
      return
    }
    try {
      await updateLabel.mutateAsync({ photoId, label: trimmed })
      setEditing(false)
    } catch (err) {
      handleMutationError(err, 'Failed to update meal name')
    }
  }

  if (editing) {
    return (
      <input
        type="text"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            commit(draft)
          } else if (e.key === 'Escape') {
            e.preventDefault()
            setDraft(label ?? '')
            setEditing(false)
          }
        }}
        onBlur={() => commit(draft)}
        disabled={updateLabel.isPending}
        autoFocus
        placeholder="Name this meal"
        aria-label="Edit meal name"
        className="w-full rounded border border-border bg-background px-1.5 py-0.5 text-sm font-semibold leading-tight focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
      />
    )
  }

  return (
    <div className="flex min-w-0 items-center gap-1">
      <button
        type="button"
        onClick={() => setEditing(true)}
        aria-label="Edit meal name"
        className="flex min-w-0 items-center gap-1 truncate text-sm font-semibold leading-tight hover:underline"
      >
        <span className="truncate">{title}</span>
        <Pencil className="size-3 shrink-0 text-muted-foreground" />
      </button>
      {!label?.trim() && dishName && (
        <button
          type="button"
          onClick={() => commit(dishName)}
          className="shrink-0 truncate text-xs text-muted-foreground hover:text-foreground hover:underline"
        >
          AI: {dishName} — Use
        </button>
      )}
    </div>
  )
}

/**
 * Bottom-sheet-style overlay for editing a single photo's ingredients with
 * comfortable spacing and large tap targets. Wraps the existing
 * `<PhotoAnalysis>` component without modifying it — just gives it room to
 * breathe. See issue #76 / mockups/v2-cards.html for the visual target.
 */
export function PhotoFocusOverlay({
  photoId,
  photos,
  mode = 'edit',
  onClose,
  onSelectPhoto,
}: PhotoFocusOverlayProps) {
  const open = photoId !== null
  const { data: analysis } = usePhotoAnalysis(photoId)
  const updateVisibility = useUpdatePhotoVisibility()
  const reducedMotion = useReducedMotion()
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const activeTabRef = useRef<HTMLButtonElement | null>(null)

  useEffect(() => {
    activeTabRef.current?.scrollIntoView({ inline: 'center', block: 'nearest' })
  }, [photoId])

  const dishName = analysis?.dish_name ?? null
  const confidence =
    analysis?.dish_confidence != null
      ? Math.round(analysis.dish_confidence * 100)
      : null

  const currentPhoto = photoId !== null ? photos.find((p) => p.id === photoId) ?? null : null
  const isSharedMeal =
    currentPhoto?.source_photo_id != null || currentPhoto?.tagged_by_handle != null
  const isHidden = currentPhoto?.hidden_at != null

  const toggleHidden = async () => {
    if (!currentPhoto) return
    try {
      await updateVisibility.mutateAsync({ photoId: currentPhoto.id, hidden: !isHidden })
    } catch (err) {
      handleMutationError(err, 'Could not update profile visibility')
    }
  }

  const { style: gestureStyle, handlers } = useSheetGestures({
    photoId,
    photos,
    onSelectPhoto,
    onClose,
    reducedMotion,
    scrollRef,
  })

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose()
      }}
    >
      <DialogContent
        showCloseButton={false}
        style={gestureStyle}
        {...handlers}
        className="fixed inset-x-0 bottom-0 top-auto m-0 translate-none grid max-h-[92vh] w-full max-w-full min-w-0 grid-cols-1 grid-rows-[auto_auto_auto_1fr] gap-0 overflow-hidden rounded-b-none rounded-t-2xl p-0 duration-200 data-open:slide-in-from-bottom data-closed:slide-out-to-bottom sm:inset-0 sm:top-0 sm:bottom-0 sm:m-auto sm:h-fit sm:max-w-2xl sm:rounded-2xl sm:data-open:slide-in-from-bottom-0 sm:data-open:zoom-in-95 sm:data-closed:slide-out-to-bottom-0 sm:data-closed:zoom-out-95"
      >
        {/* Drag handle — bottom-sheet affordance on mobile only */}
        <div data-sheet-top-region className="flex justify-center pb-1 pt-2 sm:hidden">
          <div className="h-1 w-10 rounded-full bg-border" />
        </div>

        {/* Header — no explicit close button: the sheet dismisses via swipe-down
            (mobile), backdrop click, or Esc (Dialog onOpenChange). */}
        <div data-sheet-top-region className="flex items-center gap-2 border-b border-border px-4 py-3">
          <div className="min-w-0 flex-1">
            {photoId !== null && (
              <TitleEditor
                key={photoId}
                photoId={photoId}
                label={currentPhoto?.label ?? null}
                dishName={dishName}
              />
            )}
            <div className="mt-0.5 truncate text-xs text-muted-foreground">
              {[
                currentPhoto?.tagged_by_handle
                  ? `Shared by @${currentPhoto.tagged_by_handle}`
                  : null,
                confidence != null ? `${confidence}% confident` : null,
              ]
                .filter(Boolean)
                .join(' · ') || 'Tap an ingredient to edit'}
            </div>
          </div>
          {currentPhoto && (
            <button
              type="button"
              onClick={() => void toggleHidden()}
              disabled={updateVisibility.isPending}
              className="flex shrink-0 items-center gap-1 rounded-md px-1.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
            >
              {isHidden ? (
                <Eye className="size-3.5" aria-hidden />
              ) : (
                <EyeOff className="size-3.5" aria-hidden />
              )}
              {isHidden ? 'Show on profile' : 'Hide from profile'}
            </button>
          )}
        </div>

        {/* Hero image + meal tabs */}
        <div data-sheet-top-region className="relative">
          {photoId !== null && currentPhoto && (
            photoHasImage(currentPhoto) ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={`/api/v1/photos/${photoId}/file`}
                alt={currentPhoto.label || dishName || 'Meal photo'}
                className="aspect-[4/3] w-full object-cover"
              />
            ) : (
              <div className="relative flex aspect-[4/3] w-full items-center justify-center bg-muted">
                <MealIconThumb
                  iconKey={currentPhoto.icon_key ?? 'bowl'}
                  size="lg"
                  className="size-24 rounded-2xl"
                />
                <span className="absolute left-3 top-3 rounded-full bg-background/90 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground ring-1 ring-border">
                  Library
                </span>
              </div>
            )
          )}

          {photos.length > 1 && (
            <div className="absolute inset-x-0 bottom-2 flex justify-center px-2">
              <div className="flex max-w-full snap-x snap-mandatory items-center gap-1 overflow-x-auto rounded-full border border-border bg-background/95 p-1 shadow-sm backdrop-blur [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                {photos.map((p, i) => {
                  const isActive = p.id === photoId
                  return (
                    <button
                      key={p.id}
                      ref={isActive ? activeTabRef : undefined}
                      type="button"
                      onClick={() => onSelectPhoto(p.id)}
                      aria-label={`Switch to photo ${i + 1}`}
                      aria-current={isActive ? 'true' : undefined}
                      className={
                        isActive
                          ? 'size-7 shrink-0 snap-center rounded-full bg-foreground text-xs font-semibold text-background'
                          : 'size-7 shrink-0 snap-center rounded-full text-xs text-muted-foreground hover:bg-muted'
                      }
                    >
                      {i + 1}
                    </button>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        {/* Body: existing PhotoAnalysis, reused unchanged. The surrounding wrapper
            gives it the breathing room the inline placement lacks. */}
        <div ref={scrollRef} data-sheet-scroll className="overflow-y-auto px-4 pb-4 pt-2">
          {currentPhoto && (
            <MealTimeEditor
              key={currentPhoto.id}
              photoId={currentPhoto.id}
              mealTime={currentPhoto.meal_time}
              filename={currentPhoto.filename}
            />
          )}
          {currentPhoto && (
            <div className="mb-3">
              <MealCompanionsSection photo={currentPhoto} variant="editor" />
            </div>
          )}
          {currentPhoto && <PhotoDietTagsSection photo={currentPhoto} />}
          {photoId !== null && (
            <PhotoAnalysis
              key={photoId}
              photoId={photoId}
              mode={mode}
              hideTitle
              isSharedMeal={isSharedMeal}
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
