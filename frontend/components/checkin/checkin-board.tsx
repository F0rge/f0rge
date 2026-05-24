'use client'

/**
 * CheckinBoard — V2 cards dashboard state owner.
 *
 * Pure data-entry surface. No reorder mode (that lives in /customize/reorder).
 * Cards render in the order saved in localStorage (ht.cards-v2.order), with
 * cards in ht.cards-v2.hidden filtered out.
 */

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import {
  Apple,
  BookOpen,
  Heart,
  Moon,
  Pill,
  Activity,
  Zap,
} from 'lucide-react'
import { useSupplementCatalog, useTreatments, useEntries } from '@/lib/api/hooks'
import { useAutosaveEntry } from '@/lib/hooks/use-autosave-entry'
import type { AutosaveState } from '@/lib/hooks/use-autosave-entry'
import type { Entry, EntryCreate, StoolStatus } from '@/lib/api/types'
import { computeHeroStats } from '@/lib/checkin/hero-stats'
import { DEFAULT_CARD_ORDER, loadCardOrder, loadHiddenCards, type CardId } from '@/lib/checkin/card-order'
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
}

// col-span classes per card — live here so each card carries the right grid width.
const CARD_COL_SPAN: Record<CardId, string> = {
  food:        'col-span-12',
  wellbeing:   'col-span-12 lg:col-span-4',
  gut:         'col-span-12 lg:col-span-4',
  supplements: 'col-span-12 lg:col-span-4',
  symptoms:    'col-span-12 lg:col-span-6',
  trackers:    'col-span-12 lg:col-span-6',
  notes:       'col-span-12 lg:col-span-6',
}

// Icons used in CARD_META — defined at module scope for react-hooks/static-components.
const CARD_ICONS: Record<CardId, React.ReactNode> = {
  food:        <Apple className="size-4" />,
  wellbeing:   <Moon className="size-4" />,
  gut:         <Activity className="size-4" />,
  supplements: <Pill className="size-4" />,
  symptoms:    <Zap className="size-4" />,
  trackers:    <Heart className="size-4" />,
  notes:       <BookOpen className="size-4" />,
}

// Silence unused-variable warning — icons kept here for future TierPill phase.
void CARD_ICONS

export function CheckinBoard({
  date,
  existingEntry,
  onAutosaveStateChange,
  onAutosaveFnsReady,
  onOpenPhotoFocus,
}: CheckinBoardProps) {
  const { data: catalog } = useSupplementCatalog(false)
  const { data: activeTreatments } = useTreatments(date)

  const currentMonth = date.slice(0, 7)
  const { data: monthEntries } = useEntries(currentMonth)

  const defaultSupplements = (catalog ?? [])
    .filter((c) => !c.archived)
    .map((c) => c.key)
    .join(',')

  // ── Card order state ─────────────────────────────────────────────────────
  const [cardOrder, setCardOrder] = useState<CardId[]>(() => [...DEFAULT_CARD_ORDER])
  useEffect(() => {
    const saved = loadCardOrder()
    setCardOrder((prev) =>
      prev.length === saved.length && prev.every((id, i) => id === saved[i]) ? prev : saved,
    )
  }, [])

  // ── Hidden cards state ────────────────────────────────────────────────────
  const [hiddenCards, setHiddenCards] = useState<CardId[]>([])
  useEffect(() => {
    const saved = loadHiddenCards()
    setHiddenCards((prev) =>
      prev.length === saved.length && prev.every((id, i) => id === saved[i]) ? prev : saved,
    )
  }, [])

  // Re-syncs on focus to cover bfcache restore and tab-switch — SPA navigation already
  // remounts via Next.js, but back-button to a cached page does not.
  useEffect(() => {
    const handleFocus = () => {
      const savedOrder = loadCardOrder()
      setCardOrder((prev) =>
        prev.length === savedOrder.length && prev.every((id, i) => id === savedOrder[i])
          ? prev
          : savedOrder,
      )
      const savedHidden = loadHiddenCards()
      setHiddenCards((prev) =>
        prev.length === savedHidden.length && prev.every((id, i) => id === savedHidden[i])
          ? prev
          : savedHidden,
      )
    }
    window.addEventListener('focus', handleFocus)
    return () => window.removeEventListener('focus', handleFocus)
  }, [])

  // ── Form state ───────────────────────────────────────────────────────────
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

  // ── Dirty-wrapped setters ─────────────────────────────────────────────────
  const setOverallDirty        = useCallback((v: number)      => { markDirty(); setOverall(v) },        [markDirty])
  const setBloatingDirty       = useCallback((v: number)      => { markDirty(); setBloating(v) },       [markDirty])
  const setStoolStatusDirty    = useCallback((v: StoolStatus) => { markDirty(); setStoolStatus(v) },    [markDirty])
  const setBristolTypeDirty    = useCallback((v: number|null) => { markDirty(); setBristolType(v) },    [markDirty])
  const setJointPainDirty      = useCallback((v: number)      => { markDirty(); setJointPain(v) },      [markDirty])
  const setNeuroDirty          = useCallback((v: number)      => { markDirty(); setNeuro(v) },          [markDirty])
  const setSleepQualityDirty   = useCallback((v: number)      => { markDirty(); setSleepQuality(v) },   [markDirty])
  const setStressDirty         = useCallback((v: number)      => { markDirty(); setStress(v) },         [markDirty])
  const setNotesDirty          = useCallback((v: string)      => { markDirty(); setNotes(v) },          [markDirty])
  const setSickDirty           = useCallback((v: boolean)     => { markDirty(); setSick(v) },           [markDirty])
  const setHotShowerDirty      = useCallback((v: boolean)     => { markDirty(); setHotShower(v) },      [markDirty])
  const setSymptomsJsonDirty   = useCallback((v: Record<string, number>) => { markDirty(); setSymptomsJson(v) }, [markDirty])
  const setAlcoholUnitsDirty   = useCallback((v: number)      => { markDirty(); setAlcoholUnits(v) },   [markDirty])
  const setCaffeineServingsDirty = useCallback((v: number)    => { markDirty(); setCaffeineServings(v) }, [markDirty])

  const handleSupplementChange = useCallback((v: string) => {
    markDirty()
    setSupplements(v)
    setSupplementsTouched(true)
  }, [markDirty])

  const handleSupplementTouched = useCallback(() => {
    setSupplementsTouched(true)
  }, [])

  const handleDietToggle = useCallback((id: string) => {
    markDirty()
    setDietRisk((prev) => {
      const current = prev ? prev.split(',').filter(Boolean) : []
      if (current.includes(id)) return current.filter((d) => d !== id).join(',')
      return [...current, id].join(',')
    })
  }, [markDirty])

  // ── Pre-fill effects ──────────────────────────────────────────────────────
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

  useEffect(() => {
    if (stoolStatus !== 'abnormal') {
      setBristolType(null)
    } else {
      setBristolType((prev) => prev ?? 4)
    }
  }, [stoolStatus])

  // ── Payload memo ──────────────────────────────────────────────────────────
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

  // ── Autosave ──────────────────────────────────────────────────────────────
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

  // ── Insights data ─────────────────────────────────────────────────────────
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
      photo_signal: existingEntry?.photo_signal ?? base.photo_signal,
    }
  }, [
    existingEntry, isDirty, date, overall, bloating, stoolStatus, jointPain,
    neuro, sleepQuality, stress, sick, hotShower, notes, alcoholUnits,
    caffeineServings, supplements, symptomsJson, existingPhotos,
  ])

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

  // ── Card renderers ────────────────────────────────────────────────────────
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

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-4 pb-8">
      <HeroStats data={heroStats} />

      <div className="grid grid-cols-12 gap-4 auto-rows-min">
        <TreatmentBanner
          treatments={activeTreatments ?? []}
          checkinDate={date}
        />

        {cardOrder
          .filter((id) => !hiddenCards.includes(id))
          .map((id) => (
            <div key={id} className={CARD_COL_SPAN[id]}>
              {cardRenderers[id]()}
            </div>
          ))}
      </div>
    </div>
  )
}
