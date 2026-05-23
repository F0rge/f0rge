'use client'

/**
 * CheckinBoard — V2 cards dashboard state owner.
 *
 * Replaces CheckinForm. Holds every useState the old form held plus the autosave
 * subscription. Cards are pure presentational props-in, onChange-out. No Context,
 * no Zustand. The autosave contract (payload memo, dirtyRef, forceFlush handshake
 * with PhotoCapture) is preserved verbatim.
 */

import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { useSupplementCatalog, useTreatments, useEntries } from '@/lib/api/hooks'
import { useAutosaveEntry } from '@/lib/hooks/use-autosave-entry'
import type { AutosaveState } from '@/lib/hooks/use-autosave-entry'
import type { Entry, EntryCreate, StoolStatus } from '@/lib/api/types'
import { computeHeroStats } from '@/lib/checkin/hero-stats'
import { detectPatterns } from '@/lib/checkin/patterns'
import {
  HeroStats,
  TreatmentBanner,
  FoodCard,
  InsightsCard,
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

export function CheckinBoard({
  date,
  existingEntry,
  onAutosaveStateChange,
  onAutosaveFnsReady,
  onOpenPhotoFocus,
}: CheckinBoardProps) {
  const { data: catalog } = useSupplementCatalog(false)
  const { data: activeTreatments } = useTreatments(date)

  // entries for the current month — used by InsightsCard + HeroStats.
  const currentMonth = date.slice(0, 7) // YYYY-MM
  const { data: monthEntries } = useEntries(currentMonth)

  const defaultSupplements = (catalog ?? [])
    .filter((c) => !c.archived)
    .map((c) => c.key)
    .join(',')

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
      setBristolType(existingEntry.bristol_type ?? null)
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

  // Clear Bristol when leaving abnormal state.
  useEffect(() => {
    if (stoolStatus !== 'abnormal') setBristolType(null)
  }, [stoolStatus])

  const bristolBlocked = stoolStatus === 'abnormal' && bristolType === null

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
    enabled: !bristolBlocked && isDirty,
    blocked: bristolBlocked,
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

  const todaySupplements = supplements ? supplements.split(',').filter(Boolean) : []
  const pattern = useMemo(
    () => detectPatterns(todayForStats, last7, todaySupplements),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [todayForStats, last7, supplements],
  )

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="space-y-4 pb-8">
      {/* Hero stats strip — full width above grid */}
      <HeroStats data={heroStats} />

      {/* 12-column card grid */}
      <div className="grid grid-cols-12 gap-4 auto-rows-min">
        <TreatmentBanner
          treatments={activeTreatments ?? []}
          checkinDate={date}
        />

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

        <InsightsCard
          today={todayForStats}
          last7={last7}
          pattern={pattern}
        />

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

        <GutCard
          bloating={bloating}
          onBloatingChange={setBloatingDirty}
          stoolStatus={stoolStatus}
          onStoolStatusChange={setStoolStatusDirty}
          bristolType={bristolType}
          onBristolTypeChange={setBristolTypeDirty}
          jointPain={jointPain}
          onJointPainChange={setJointPainDirty}
          bristolBlocked={bristolBlocked}
        />

        <SupplementsCard
          value={supplements}
          onChange={handleSupplementChange}
          onTouched={handleSupplementTouched}
        />

        <SymptomsCard
          value={symptomsJson}
          onChange={setSymptomsJsonDirty}
        />

        <TrackersCard
          alcoholUnits={alcoholUnits}
          onAlcoholUnitsChange={setAlcoholUnitsDirty}
          caffeineServings={caffeineServings}
          onCaffeineServingsChange={setCaffeineServingsDirty}
          sick={sick}
          onSickChange={setSickDirty}
          hotShower={hotShower}
          onHotShowerChange={setHotShowerDirty}
        />

        <NotesCard
          value={notes}
          onChange={setNotesDirty}
          onBlur={handleBlur}
        />
      </div>
    </div>
  )
}
