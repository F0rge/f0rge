'use client'

/**
 * CheckinBoard — V2 cards dashboard state owner.
 *
 * Replaces CheckinForm. Holds every useState the old form held plus the autosave
 * subscription. Cards are pure presentational props-in, onChange-out. No Context,
 * no Zustand. The autosave contract (payload memo, dirtyRef, forceFlush handshake
 * with PhotoCapture) is preserved verbatim.
 *
 * Card reordering uses a dedicated reorder mode (isReorderMode). In normal mode
 * there are no drag handles and no DndContext overhead. In reorder mode, cards
 * collapse to uniform tiles with drag grips and up/down arrow buttons — no
 * card morphing is possible because all tiles have the same height.
 */

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import {
  DndContext,
  DragOverlay,
  closestCenter,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  arrayMove,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import {
  Activity,
  Apple,
  BookOpen,
  Heart,
  Moon,
  Pill,
  Zap,
} from 'lucide-react'
import { useSupplementCatalog, useTreatments, useEntries } from '@/lib/api/hooks'
import { useAutosaveEntry } from '@/lib/hooks/use-autosave-entry'
import type { AutosaveState } from '@/lib/hooks/use-autosave-entry'
import type { Entry, EntryCreate, StoolStatus } from '@/lib/api/types'
import { computeHeroStats } from '@/lib/checkin/hero-stats'
import { DEFAULT_CARD_ORDER, loadCardOrder, saveCardOrder, loadHiddenCards, saveHiddenCards, type CardId } from '@/lib/checkin/card-order'
import {
  HeroStats,
  TreatmentBanner,
  FoodCard,
  WellbeingCard,
  GutCard,
  SupplementsCard,
  SymptomsCard,
  TrackersCard,
  NotesCard,
} from './cards'
import { SortableCard } from './cards/sortable-card'
import { ReorderTile } from './cards/reorder-tile'
import type { CardMeta } from './cards/reorder-tile'

interface AutosaveFns {
  flush: () => void
  forceFlush: () => Promise<void>
  retry: () => void
  flushBeacon: () => void
}

interface CheckinBoardProps {
  date: string
  existingEntry?: Entry | null
  onAutosaveStateChange?: (state: AutosaveState) => void
  onAutosaveFnsReady?: (fns: AutosaveFns) => void
  onOpenPhotoFocus?: (photoId: number) => void
  /** Called whenever the user saves a new card order to localStorage. */
  onCardOrderChange?: () => void
  /** Controlled reorder mode — set by page header button. Defaults to false. */
  isReorderMode?: boolean
}

// Card metadata (icon + label) for reorder tiles.
// Defined at module scope to satisfy react-hooks/static-components rule.
const CARD_META: Record<CardId, CardMeta> = {
  food:        { id: 'food',        icon: <Apple className="size-4" />,    label: 'Food & Diet' },
  wellbeing:   { id: 'wellbeing',   icon: <Moon className="size-4" />,     label: 'Wellbeing' },
  gut:         { id: 'gut',         icon: <Activity className="size-4" />, label: 'Gut' },
  supplements: { id: 'supplements', icon: <Pill className="size-4" />,     label: 'Supplements' },
  symptoms:    { id: 'symptoms',    icon: <Zap className="size-4" />,      label: 'Symptoms' },
  trackers:    { id: 'trackers',    icon: <Heart className="size-4" />,    label: 'Trackers' },
  notes:       { id: 'notes',       icon: <BookOpen className="size-4" />, label: 'Notes' },
}

export function CheckinBoard({
  date,
  existingEntry,
  onAutosaveStateChange,
  onAutosaveFnsReady,
  onOpenPhotoFocus,
  onCardOrderChange,
  isReorderMode = false,
}: CheckinBoardProps) {
  const { data: catalog } = useSupplementCatalog(false)
  const { data: activeTreatments } = useTreatments(date)

  // entries for the current month — used by HeroStats.
  const currentMonth = date.slice(0, 7) // YYYY-MM
  const { data: monthEntries } = useEntries(currentMonth)

  const defaultSupplements = (catalog ?? [])
    .filter((c) => !c.archived)
    .map((c) => c.key)
    .join(',')

  // ── Card order state ────────────────────────────────────────────────────
  // Start with DEFAULT so SSR + client first paint agree (localStorage is client-only).
  // Swap in any saved order via useEffect on mount; one-frame default→saved is acceptable.
  const [cardOrder, setCardOrder] = useState<CardId[]>(() => [...DEFAULT_CARD_ORDER])
  useEffect(() => {
    const saved = loadCardOrder()
    setCardOrder((prev) =>
      prev.length === saved.length && prev.every((id, i) => id === saved[i]) ? prev : saved,
    )
  }, [])

  // ── Hidden cards state ───────────────────────────────────────────────────
  // Same SSR-safe pattern as cardOrder: start empty, swap in from localStorage on mount.
  const [hiddenCards, setHiddenCards] = useState<CardId[]>([])
  useEffect(() => {
    const saved = loadHiddenCards()
    setHiddenCards((prev) =>
      prev.length === saved.length && prev.every((id, i) => id === saved[i]) ? prev : saved,
    )
  }, [])

  const handleToggleHidden = useCallback((id: CardId) => {
    setHiddenCards((prev) => {
      const next = prev.includes(id) ? prev.filter((h) => h !== id) : [...prev, id]
      saveHiddenCards(next)
      return next
    })
  }, [])

  // ── Drag state — only used in reorder mode ──────────────────────────────
  // In reorder mode, tiles are uniform height so no width capture is needed.
  const [activeId, setActiveId] = useState<CardId | null>(null)

  // In reorder mode, pointer drag needs no distance constraint (tiles have no
  // inner interactive content). Touch drag also needs no long-press delay —
  // the tile IS the drag target, there's nothing else to tap inside it.
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 4 },
    }),
    useSensor(TouchSensor, {
      activationConstraint: { delay: 150, tolerance: 8 },
    }),
  )

  const handleDragStart = useCallback((event: DragStartEvent) => {
    setActiveId(event.active.id as CardId)
  }, [])

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    setActiveId(null)
    const { active, over } = event
    if (!over || active.id === over.id) return
    setCardOrder((prev) => {
      const oldIndex = prev.indexOf(active.id as CardId)
      const newIndex = prev.indexOf(over.id as CardId)
      const next = arrayMove(prev, oldIndex, newIndex)
      saveCardOrder(next)
      return next
    })
    onCardOrderChange?.()
  }, [onCardOrderChange])

  const handleDragCancel = useCallback(() => {
    setActiveId(null)
  }, [])

  // ── Arrow (tap-to-move) handlers ────────────────────────────────────────
  const handleMoveUp = useCallback((id: CardId) => {
    setCardOrder((prev) => {
      const idx = prev.indexOf(id)
      if (idx <= 0) return prev
      const next = arrayMove(prev, idx, idx - 1)
      saveCardOrder(next)
      return next
    })
    onCardOrderChange?.()
  }, [onCardOrderChange])

  const handleMoveDown = useCallback((id: CardId) => {
    setCardOrder((prev) => {
      const idx = prev.indexOf(id)
      if (idx < 0 || idx >= prev.length - 1) return prev
      const next = arrayMove(prev, idx, idx + 1)
      saveCardOrder(next)
      return next
    })
    onCardOrderChange?.()
  }, [onCardOrderChange])

  // ── Form state (mirrors checkin-form.tsx exactly) ──────────────────────
  const [overall, setOverall] = useState(2)
  const [bloating, setBloating] = useState(0)
  const [stoolStatus, setStoolStatus] = useState<StoolStatus>('normal')
  const [bristolType, setBristolType] = useState<number | null>(null)
  const [jointPain, setJointPain] = useState(0)
  const [neuro, setNeuro] = useState(0)
  const [sleepQuality, setSleepQuality] = useState(2)
  const [stress, setStress] = useState(1)
  const [dietRisk, setDietRisk] = useState<string>('')
  const [supplements, setSupplements] = useState<string>('')
  const [supplementsTouched, setSupplementsTouched] = useState(false)
  const [symptomsJson, setSymptomsJson] = useState<Record<string, number>>({})
  const [sick, setSick] = useState(false)
  const [hotShower, setHotShower] = useState(false)
  const [notes, setNotes] = useState('')
  const [existingPhotos, setExistingPhotos] = useState<Entry['photos']>([])
  const [alcoholUnits, setAlcoholUnits] = useState(0)
  const [caffeineServings, setCaffeineServings] = useState(0)

  const dirtyRef = useRef(false)
  const [isDirty, setIsDirty] = useState(false)
  const markDirty = useCallback(() => {
    if (!dirtyRef.current) {
      dirtyRef.current = true
      setIsDirty(true)
    }
  }, [])

  // ── Dirty-wrapped setters ───────────────────────────────────────────────
  const setOverallDirty = useCallback((v: number) => { markDirty(); setOverall(v) }, [markDirty])
  const setBloatingDirty = useCallback((v: number) => { markDirty(); setBloating(v) }, [markDirty])
  const setStoolStatusDirty = useCallback((v: StoolStatus) => { markDirty(); setStoolStatus(v) }, [markDirty])
  const setBristolTypeDirty = useCallback((v: number | null) => { markDirty(); setBristolType(v) }, [markDirty])
  const setJointPainDirty = useCallback((v: number) => { markDirty(); setJointPain(v) }, [markDirty])
  const setNeuroDirty = useCallback((v: number) => { markDirty(); setNeuro(v) }, [markDirty])
  const setSleepQualityDirty = useCallback((v: number) => { markDirty(); setSleepQuality(v) }, [markDirty])
  const setStressDirty = useCallback((v: number) => { markDirty(); setStress(v) }, [markDirty])
  const setNotesDirty = useCallback((v: string) => { markDirty(); setNotes(v) }, [markDirty])
  const setSickDirty = useCallback((v: boolean) => { markDirty(); setSick(v) }, [markDirty])
  const setHotShowerDirty = useCallback((v: boolean) => { markDirty(); setHotShower(v) }, [markDirty])
  const setSymptomsJsonDirty = useCallback((v: Record<string, number>) => { markDirty(); setSymptomsJson(v) }, [markDirty])
  const setAlcoholUnitsDirty = useCallback((v: number) => { markDirty(); setAlcoholUnits(v) }, [markDirty])
  const setCaffeineServingsDirty = useCallback((v: number) => { markDirty(); setCaffeineServings(v) }, [markDirty])

  // Supplement changes need both markDirty AND the touched flag.
  const handleSupplementChange = useCallback((v: string) => {
    markDirty()
    setSupplements(v)
    setSupplementsTouched(true)
  }, [markDirty])

  const handleSupplementTouched = useCallback(() => {
    setSupplementsTouched(true)
  }, [])

  // ── Diet toggle ─────────────────────────────────────────────────────────
  const handleDietToggle = useCallback((id: string) => {
    markDirty()
    setDietRisk((prev) => {
      const current = prev ? prev.split(',').filter(Boolean) : []
      if (current.includes(id)) return current.filter((d) => d !== id).join(',')
      return [...current, id].join(',')
    })
  }, [markDirty])

  // ── Pre-fill effects ────────────────────────────────────────────────────
  useEffect(() => {
    if (!existingEntry && !supplementsTouched && defaultSupplements) {
      setSupplements(defaultSupplements)
    }
  }, [defaultSupplements, existingEntry, supplementsTouched])

  useEffect(() => {
    if (existingEntry) {
      setOverall(existingEntry.overall)
      setBloating(existingEntry.bloating)
      if (existingEntry.stool_status) {
        setStoolStatus(existingEntry.stool_status)
      } else if (existingEntry.stool_normal === false) {
        setStoolStatus('abnormal')
      } else {
        setStoolStatus('normal')
      }
      // Default to 4 when entry was saved with abnormal stool but no bristol type.
      // Prevents autosave being gated on load for pre-existing entries.
      const resolvedStool = existingEntry.stool_status
        ?? (existingEntry.stool_normal === false ? 'abnormal' : 'normal')
      const resolvedBristol = existingEntry.bristol_type
        ?? (resolvedStool === 'abnormal' ? 4 : null)
      setBristolType(resolvedBristol)
      setJointPain(existingEntry.joint_pain)
      setNeuro(existingEntry.neuro)
      setSleepQuality(existingEntry.sleep_quality)
      setStress(existingEntry.stress)
      setDietRisk(
        existingEntry.user_added_flags !== undefined
          ? existingEntry.user_added_flags.join(',')
          : existingEntry.diet_risk,
      )
      setSupplements(existingEntry.supplements)
      setSupplementsTouched(true)
      setSymptomsJson(existingEntry.symptoms_json ?? {})
      setSick(existingEntry.sick)
      setHotShower(existingEntry.hot_shower ?? false)
      setNotes(existingEntry.notes || '')
      setAlcoholUnits(existingEntry.alcohol_units ?? 0)
      setCaffeineServings(existingEntry.caffeine_servings ?? 0)
      setExistingPhotos(existingEntry.photos || [])
    }
  }, [existingEntry])

  // Manage Bristol type based on stool status:
  // - Leaving abnormal: clear bristol (it only applies to abnormal).
  // - Entering abnormal with no bristol set: default to 4 so autosave is never gated.
  useEffect(() => {
    if (stoolStatus !== 'abnormal') {
      setBristolType(null)
    } else {
      setBristolType((prev) => prev ?? 4)
    }
  }, [stoolStatus])

  // ── Payload memo ────────────────────────────────────────────────────────
  const payload = useMemo<EntryCreate>(() => ({
    date,
    schema_version: 2,
    overall,
    bloating,
    stool_status: stoolStatus,
    bristol_type: stoolStatus === 'abnormal' && bristolType !== null ? bristolType : undefined,
    joint_pain: jointPain,
    neuro,
    sleep_quality: sleepQuality,
    stress,
    diet_risk: dietRisk,
    supplements,
    sick,
    hot_shower: hotShower,
    notes,
    alcohol_units: alcoholUnits,
    caffeine_servings: caffeineServings,
    symptoms_json: symptomsJson,
  }), [
    date, overall, bloating, stoolStatus, bristolType, jointPain, neuro,
    sleepQuality, stress, dietRisk, supplements, sick, hotShower, notes,
    alcoholUnits, caffeineServings, symptomsJson,
  ])

  // ── Autosave ────────────────────────────────────────────────────────────
  const autosave = useAutosaveEntry({
    date,
    payload,
    enabled: isDirty,
    blocked: false,
    hasExistingEntry: !!existingEntry,
  })

  useEffect(() => {
    onAutosaveStateChange?.({
      status: autosave.status,
      lastSavedAt: autosave.lastSavedAt,
      errorMessage: autosave.errorMessage,
    })
  }, [autosave.status, autosave.lastSavedAt, autosave.errorMessage, onAutosaveStateChange])

  const autosaveRef = useRef(autosave)
  useEffect(() => { autosaveRef.current = autosave })
  useEffect(() => {
    onAutosaveFnsReady?.({
      flush: () => autosaveRef.current.flush(),
      forceFlush: () => autosaveRef.current.forceFlush(),
      retry: () => autosaveRef.current.retry(),
      flushBeacon: () => autosaveRef.current.flushBeacon(),
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // intentionally empty — register once

  const handleBlur = useCallback(() => { autosave.flush() }, [autosave])

  // ── Insights data ────────────────────────────────────────────────────────
  // Build a synthetic "today" entry from current form state for live hero/sparkline updates.
  const todayForStats = useMemo<Entry | null>(() => {
    if (!existingEntry && !isDirty) return null
    const base: Entry = existingEntry ?? {
      id: -1, date, schema_version: 2, entry_time: null, period_of_day: null,
      overall: 2, bloating: 0, stool_status: 'normal', stool_normal: null, stool_type: null,
      bristol_type: null, joint_pain: 0, neuro: 0, sleep_quality: 2, stress: 1,
      diet_risk: '', supplements: '', sick: false, notes: null,
      alcohol_units: null, caffeine_servings: null,
      effective_flags: [], photo_derived_flags: [], user_added_flags: [],
      photo_signal: { flags: [], scores: { histamine_load: 0, fodmap_count: 0, gluten_count: 0, dairy_count: 0 }, sources: {} },
      symptoms_json: null, hot_shower: false,
      photos: [], created_at: '', updated_at: '',
    }
    return {
      ...base,
      overall, bloating, stool_status: stoolStatus, joint_pain: jointPain,
      neuro, sleep_quality: sleepQuality, stress, sick, hot_shower: hotShower,
      notes, alcohol_units: alcoholUnits, caffeine_servings: caffeineServings,
      supplements, symptoms_json: symptomsJson,
      photos: existingPhotos,
      // photo_signal comes only from the server (existingEntry); form changes don't affect it
      photo_signal: existingEntry?.photo_signal ?? base.photo_signal,
    }
  }, [
    existingEntry, isDirty, date, overall, bloating, stoolStatus, jointPain,
    neuro, sleepQuality, stress, sick, hotShower, notes, alcoholUnits,
    caffeineServings, supplements, symptomsJson, existingPhotos,
  ])

  // Slice last 7 days (excluding today) from month entries.
  const last7 = useMemo(() => {
    if (!monthEntries) return []
    return monthEntries
      .filter((e) => e.date < date)
      .sort((a, b) => b.date.localeCompare(a.date))
      .slice(0, 7)
  }, [monthEntries, date])

  const heroStats = useMemo(
    () => computeHeroStats(todayForStats, last7, activeTreatments ?? [], date),
    [todayForStats, last7, activeTreatments, date],
  )

  // ── Card renderers + col-span map ────────────────────────────────────────
  // col-span classes live here so SortableCard can apply them to its wrapper div.
  // The inner Card components no longer carry col-span classes.
  const CARD_COL_SPAN: Record<CardId, string> = {
    food:        'col-span-12',
    wellbeing:   'col-span-12 lg:col-span-4',
    gut:         'col-span-12 lg:col-span-4',
    supplements: 'col-span-12 lg:col-span-4',
    symptoms:    'col-span-12 lg:col-span-6',
    trackers:    'col-span-12 lg:col-span-6',
    notes:       'col-span-12 lg:col-span-6',
  }

  const cardRenderers: Record<CardId, () => React.ReactNode> = {
    food: () => (
      <FoodCard
        date={date}
        existingEntry={existingEntry}
        existingPhotos={existingPhotos}
        dietRisk={dietRisk}
        onDietToggle={handleDietToggle}
        onPhotosChange={setExistingPhotos}
        ensureEntryExists={autosave.forceFlush}
        onEntryEnsured={markDirty}
        onOpenPhotoFocus={onOpenPhotoFocus}
      />
    ),
    wellbeing: () => (
      <WellbeingCard
        overall={overall}
        onOverallChange={setOverallDirty}
        sleepQuality={sleepQuality}
        onSleepQualityChange={setSleepQualityDirty}
        stress={stress}
        onStressChange={setStressDirty}
        neuro={neuro}
        onNeuroChange={setNeuroDirty}
      />
    ),
    gut: () => (
      <GutCard
        bloating={bloating}
        onBloatingChange={setBloatingDirty}
        stoolStatus={stoolStatus}
        onStoolStatusChange={setStoolStatusDirty}
        bristolType={bristolType}
        onBristolTypeChange={setBristolTypeDirty}
        jointPain={jointPain}
        onJointPainChange={setJointPainDirty}
      />
    ),
    supplements: () => (
      <SupplementsCard
        value={supplements}
        onChange={handleSupplementChange}
        onTouched={handleSupplementTouched}
      />
    ),
    symptoms: () => (
      <SymptomsCard
        value={symptomsJson}
        onChange={setSymptomsJsonDirty}
      />
    ),
    trackers: () => (
      <TrackersCard
        alcoholUnits={alcoholUnits}
        onAlcoholUnitsChange={setAlcoholUnitsDirty}
        caffeineServings={caffeineServings}
        onCaffeineServingsChange={setCaffeineServingsDirty}
        sick={sick}
        onSickChange={setSickDirty}
        hotShower={hotShower}
        onHotShowerChange={setHotShowerDirty}
        date={date}
      />
    ),
    notes: () => (
      <NotesCard
        value={notes}
        onChange={setNotesDirty}
        onBlur={handleBlur}
      />
    ),
  }

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="space-y-4 pb-8">
      {/* Hero stats strip — full width above grid, NOT sortable */}
      <HeroStats data={heroStats} />

      {isReorderMode ? (
        // ── Reorder mode: vertical list of uniform tiles ─────────────────
        // All tiles are full-width (col-span-12), same height — no morphing.
        // verticalListSortingStrategy is correct here since it IS a single column.
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
          onDragCancel={handleDragCancel}
        >
          <SortableContext items={cardOrder} strategy={verticalListSortingStrategy}>
            <div className="flex flex-col gap-2">
              {cardOrder.map((id, index) => (
                <SortableCard
                  key={id}
                  id={id}
                  colSpanClass=""
                  meta={CARD_META[id]}
                  isReorderMode={true}
                  index={index}
                  total={cardOrder.length}
                  onMoveUp={() => handleMoveUp(id)}
                  onMoveDown={() => handleMoveDown(id)}
                  isHidden={hiddenCards.includes(id)}
                  onToggleHidden={() => handleToggleHidden(id)}
                >
                  {/* children not rendered in reorder mode */}
                  {null}
                </SortableCard>
              ))}
            </div>
          </SortableContext>

          {/* DragOverlay: uniform tile, no width capture needed (full-width list) */}
          <DragOverlay>
            {activeId !== null ? (
              <ReorderTile
                meta={CARD_META[activeId]}
                dragListeners={undefined}
                isDragging={true}
                isFirst={false}
                isLast={false}
                onMoveUp={() => {}}
                onMoveDown={() => {}}
              />
            ) : null}
          </DragOverlay>
        </DndContext>
      ) : (
        // ── Normal mode: 12-column card grid, no drag ────────────────────
        <div className="grid grid-cols-12 gap-4 auto-rows-min">
          {/* Treatment banner — fixed position, not sortable */}
          <TreatmentBanner
            treatments={activeTreatments ?? []}
            checkinDate={date}
          />

          {cardOrder
            .filter((id) => !hiddenCards.includes(id))
            .map((id, index, visibleOrder) => (
              <SortableCard
                key={id}
                id={id}
                colSpanClass={CARD_COL_SPAN[id]}
                meta={CARD_META[id]}
                isReorderMode={false}
                index={index}
                total={visibleOrder.length}
                onMoveUp={() => handleMoveUp(id)}
                onMoveDown={() => handleMoveDown(id)}
              >
                {cardRenderers[id]()}
              </SortableCard>
            ))}
        </div>
      )}
    </div>
  )
}
