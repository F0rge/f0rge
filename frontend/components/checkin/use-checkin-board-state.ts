'use client'

import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { useSupplementCatalog } from '@/lib/api/hooks'
import { useAutosaveEntry } from '@/lib/hooks/use-autosave-entry'
import type { AutosaveState } from '@/lib/hooks/use-autosave-entry'
import type { Entry, EntryCreate, MedicationIntake, StoolStatus } from '@/lib/api/types'
import { DEFAULT_CARD_ORDER, loadCardOrder, loadHiddenCards, type CardId } from '@/lib/checkin/card-order'

interface AutosaveFns {
  flush: () => void
  forceFlush: () => Promise<void>
  retry: () => void
  flushBeacon: () => void
}

interface UseCheckinBoardStateOptions {
  date: string
  existingEntry?: Entry | null
  onAutosaveStateChange?: (state: AutosaveState) => void
  onAutosaveFnsReady?: (fns: AutosaveFns) => void
}

export function useCheckinBoardState({
  date,
  existingEntry,
  onAutosaveStateChange,
  onAutosaveFnsReady,
}: UseCheckinBoardStateOptions) {
  const { data: catalog } = useSupplementCatalog(false)

  const defaultSupplements = (catalog ?? [])
    .filter((c) => !c.archived)
    .map((c) => c.key)
    .join(',')

  const [cardOrder, setCardOrder] = useState<CardId[]>(() => [...DEFAULT_CARD_ORDER])
  useEffect(() => {
    const saved = loadCardOrder()
    setCardOrder((prev) =>
      prev.length === saved.length && prev.every((id, i) => id === saved[i]) ? prev : saved,
    )
  }, [])

  const [hiddenCards, setHiddenCards] = useState<CardId[]>([])
  useEffect(() => {
    const saved = loadHiddenCards()
    setHiddenCards((prev) =>
      prev.length === saved.length && prev.every((id, i) => id === saved[i]) ? prev : saved,
    )
  }, [])

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

  const [overall, setOverall] = useState(2)
  const [bloating, setBloating] = useState(0)
  const [stoolStatus, setStoolStatus] = useState<StoolStatus>('normal')
  const [bristolType, setBristolType] = useState<number | null>(null)
  const [stoolCompleteness, setStoolCompleteness] = useState<'complete' | 'incomplete' | null>(null)
  const [jointPain, setJointPain] = useState(0)
  const [neuro, setNeuro] = useState(0)
  const [sleepQuality, setSleepQuality] = useState(2)
  const [stress, setStress] = useState(1)
  const [dietRisk, setDietRisk] = useState<string>('')
  const [supplements, setSupplements] = useState<string>('')
  const [supplementsTouched, setSupplementsTouched] = useState(false)
  const [medications, setMedications] = useState<MedicationIntake[]>([])
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

  const setOverallDirty = useCallback((v: number) => { markDirty(); setOverall(v) }, [markDirty])
  const setBloatingDirty = useCallback((v: number) => { markDirty(); setBloating(v) }, [markDirty])
  const setStoolStatusDirty = useCallback((v: StoolStatus) => { markDirty(); setStoolStatus(v) }, [markDirty])
  const setBristolTypeDirty = useCallback((v: number | null) => { markDirty(); setBristolType(v) }, [markDirty])
  const setStoolCompletenessDirty = useCallback(
    (v: 'complete' | 'incomplete') => { markDirty(); setStoolCompleteness(v) },
    [markDirty],
  )
  const setJointPainDirty = useCallback((v: number) => { markDirty(); setJointPain(v) }, [markDirty])
  const setNeuroDirty = useCallback((v: number) => { markDirty(); setNeuro(v) }, [markDirty])
  const setSleepQualityDirty = useCallback((v: number) => { markDirty(); setSleepQuality(v) }, [markDirty])
  const setStressDirty = useCallback((v: number) => { markDirty(); setStress(v) }, [markDirty])
  const setNotesValue = useCallback((v: string) => { setNotes(v) }, [])
  const setSickDirty = useCallback((v: boolean) => { markDirty(); setSick(v) }, [markDirty])
  const setHotShowerDirty = useCallback((v: boolean) => { markDirty(); setHotShower(v) }, [markDirty])
  const setSymptomsJsonDirty = useCallback(
    (v: Record<string, number>) => { markDirty(); setSymptomsJson(v) },
    [markDirty],
  )
  const setMedicationsDirty = useCallback(
    (v: MedicationIntake[]) => { markDirty(); setMedications(v) },
    [markDirty],
  )
  const setAlcoholUnitsDirty = useCallback((v: number) => { markDirty(); setAlcoholUnits(v) }, [markDirty])
  const setCaffeineServingsDirty = useCallback(
    (v: number) => { markDirty(); setCaffeineServings(v) },
    [markDirty],
  )

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
      setStoolCompleteness(existingEntry.stool_completeness ?? null)
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
      setMedications(existingEntry.medications ?? [])
      setSymptomsJson(existingEntry.symptoms_json ?? {})
      setSick(existingEntry.sick)
      setHotShower(existingEntry.hot_shower ?? false)
      setNotes(existingEntry.notes || '')
      setAlcoholUnits(existingEntry.alcohol_units ?? 0)
      setCaffeineServings(existingEntry.caffeine_servings ?? 0)
      setExistingPhotos(existingEntry.photos || [])
    }
  }, [existingEntry])

  const fivePoint = (existingEntry?.schema_version ?? 4) >= 4

  useEffect(() => {
    if (stoolStatus !== 'abnormal') {
      setBristolType(null)
    } else {
      setBristolType((prev) => prev ?? 4)
    }
  }, [stoolStatus])

  const payload = useMemo<EntryCreate>(() => ({
    date,
    overall,
    bloating,
    stool_status: stoolStatus,
    bristol_type: stoolStatus === 'abnormal' && bristolType !== null ? bristolType : undefined,
    stool_completeness: stoolCompleteness ?? undefined,
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
    medications,
  }), [
    date, overall, bloating, stoolStatus, bristolType, stoolCompleteness, jointPain, neuro,
    sleepQuality, stress, dietRisk, supplements, sick, hotShower, notes,
    alcoholUnits, caffeineServings, symptomsJson, medications,
  ])

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
  const notesDraftFlushRef = useRef<(() => void) | null>(null)
  const registerNotesDraftFlush = useCallback((flush: () => void) => {
    notesDraftFlushRef.current = flush
  }, [])

  useEffect(() => { autosaveRef.current = autosave })
  useEffect(() => {
    const flushNotesDraft = () => notesDraftFlushRef.current?.()
    onAutosaveFnsReady?.({
      flush: () => {
        flushNotesDraft()
        autosaveRef.current.flush()
      },
      forceFlush: async () => {
        flushNotesDraft()
        await autosaveRef.current.forceFlush()
      },
      retry: () => autosaveRef.current.retry(),
      flushBeacon: () => {
        flushNotesDraft()
        autosaveRef.current.flushBeacon()
      },
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleBlur = useCallback(() => { autosave.flush() }, [autosave])

  return {
    cardOrder,
    hiddenCards,
    fivePoint,
    existingPhotos,
    setExistingPhotos,
    dietRisk,
    handleDietToggle,
    handleSupplementChange,
    handleSupplementTouched,
    handleBlur,
    markDirty,
    autosave,
    overall,
    setOverallDirty,
    sleepQuality,
    setSleepQualityDirty,
    stress,
    setStressDirty,
    neuro,
    setNeuroDirty,
    bloating,
    setBloatingDirty,
    stoolStatus,
    setStoolStatusDirty,
    bristolType,
    setBristolTypeDirty,
    stoolCompleteness,
    setStoolCompletenessDirty,
    jointPain,
    setJointPainDirty,
    supplements,
    medications,
    setMedicationsDirty,
    symptomsJson,
    setSymptomsJsonDirty,
    alcoholUnits,
    setAlcoholUnitsDirty,
    caffeineServings,
    setCaffeineServingsDirty,
    sick,
    setSickDirty,
    hotShower,
    setHotShowerDirty,
    notes,
    setNotesValue,
    registerNotesDraftFlush,
  }
}

export type CheckinBoardState = ReturnType<typeof useCheckinBoardState>
