'use client'

import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import Link from 'next/link'
import { Camera, Pill } from 'lucide-react'
import { ScaleInput } from './scale-input'
import { BinaryInput } from './binary-input'
import { BristolInput } from './bristol-input'
import { NotesInput } from './notes-input'
import { PhotoCapture } from './photo-capture'
import { SupplementPicker } from './supplement-picker'
import { SymptomPicker } from './symptom-picker'
import { Stepper } from '@/components/ui/stepper'
import { useSupplementCatalog, useTreatments } from '@/lib/api/hooks'
import { PhotoAnalysis } from '@/components/shared/food-analysis'
import { useAutosaveEntry } from '@/lib/hooks/use-autosave-entry'
import type { AutosaveState } from '@/lib/hooks/use-autosave-entry'
import type { Entry, EntryCreate, PhotoSignal, StoolStatus } from '@/lib/api/types'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { useDeletePhoto } from '@/lib/api/hooks'
import { X } from 'lucide-react'

const DIET_OPTIONS = [
  { id: 'high-histamine', label: 'High-histamine' },
  { id: 'high-fodmap', label: 'High-FODMAP' },
  { id: 'gluten', label: 'Gluten' },
  { id: 'dairy', label: 'Dairy' },
]

// Score to display on the locked chip for each flag.
function getFlagScore(flag: string, signal: PhotoSignal): number {
  switch (flag) {
    case 'high-histamine': return signal.scores.histamine_load
    case 'high-fodmap': return signal.scores.fodmap_count
    case 'gluten': return signal.scores.gluten_count
    case 'dairy': return signal.scores.dairy_count
    default: return 0
  }
}

// Build a human-readable attribution line from signal.sources.
function buildSourceLine(signal: PhotoSignal): string {
  return signal.flags
    .map((flag) => {
      const ingredients = signal.sources[flag]
      if (!ingredients || ingredients.length === 0) return null
      return `${DIET_OPTIONS.find((o) => o.id === flag)?.label ?? flag}: ${ingredients.join(', ')}`
    })
    .filter(Boolean)
    .join(' · ')
}

interface LockedChipProps {
  flag: string
  label: string
  score: number
  title: string
}

function LockedChip({ flag, label, score, title }: LockedChipProps) {
  return (
    <span
      key={flag}
      title={title}
      className={[
        'inline-flex items-center gap-2 min-h-[48px]',
        'rounded-xl border border-primary bg-foreground text-primary-foreground',
        'px-3 py-2.5 text-sm font-medium cursor-not-allowed shadow-sm',
      ].join(' ')}
    >
      <span className="inline-flex size-[18px] shrink-0 items-center justify-center rounded-full bg-white/20">
        <Camera className="size-2.5" />
      </span>
      {label}
      <span
        className={[
          'inline-flex min-w-[22px] h-[22px] items-center justify-center',
          'rounded-full px-1.5 text-xs font-bold bg-white/20 text-primary-foreground',
          'tabular-nums',
        ].join(' ')}
      >
        {score}
      </span>
    </span>
  )
}

interface PhotoDerivedRowProps {
  signal: PhotoSignal
  photoCount: number
}

function PhotoDerivedRow({ signal, photoCount }: PhotoDerivedRowProps) {
  const sourceLine = buildSourceLine(signal)

  const ingredientCount = Object.values(signal.sources).reduce(
    (sum, arr) => sum + arr.length,
    0,
  )

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Camera className="size-3.5" />
          From photos (locked)
        </div>
        <span className="text-xs text-muted-foreground">
          {photoCount} {photoCount === 1 ? 'photo' : 'photos'} &middot; {ingredientCount} ingredients
        </span>
      </div>

      {signal.flags.length > 0 ? (
        <>
          <div className="flex flex-wrap gap-2">
            {signal.flags.map((flag) => {
              const opt = DIET_OPTIONS.find((o) => o.id === flag)
              const score = getFlagScore(flag, signal)
              const sources = signal.sources[flag] ?? []
              const flagLabel = opt?.label ?? flag
              const scoreDescription =
                flag === 'high-histamine'
                  ? `Σ histamine_score = ${score}`
                  : `${score} ingredient${score !== 1 ? 's' : ''}`
              return (
                <LockedChip
                  key={flag}
                  flag={flag}
                  label={flagLabel}
                  score={score}
                  title={`${scoreDescription}${sources.length > 0 ? `: ${sources.join(', ')}` : ''}`}
                />
              )
            })}
          </div>
          {sourceLine && (
            <p className="text-[0.7rem] leading-[1.4] text-muted-foreground">{sourceLine}</p>
          )}
        </>
      ) : (
        <p className="text-xs text-muted-foreground">Photos confirmed — no risk flags detected.</p>
      )}
    </div>
  )
}

interface DietRiskSectionProps {
  existingEntry?: Entry | null
  existingPhotos: Entry['photos']
  dietRisk: string
  onToggle: (id: string) => void
}

function DietRiskSection({ existingEntry, existingPhotos, dietRisk, onToggle }: DietRiskSectionProps) {
  const hasPhotos = existingPhotos.length > 0
  const signal: PhotoSignal = existingEntry?.photo_signal ?? {
    flags: [],
    scores: { histamine_load: 0, fodmap_count: 0, gluten_count: 0, dairy_count: 0 },
    sources: {},
  }

  const signalIsLive = signal.flags.length > 0 || signal.scores.histamine_load > 0

  const manualOptions = DIET_OPTIONS.filter((o) => !signal.flags.includes(o.id))
  const selectedFlags = dietRisk ? dietRisk.split(',').filter(Boolean) : []

  return (
    <div className="space-y-3">
      <label className="text-sm font-semibold">Diet risk</label>

      {hasPhotos ? (
        signalIsLive ? (
          <PhotoDerivedRow signal={signal} photoCount={existingPhotos.length} />
        ) : (
          <div className="rounded-xl border border-dashed border-border bg-background p-3">
            <div className="flex items-center gap-1.5 text-muted-foreground">
              <Camera className="size-3.5" />
              <span className="text-xs">Photos still analyzing — flags will update once confirmed.</span>
            </div>
          </div>
        )
      ) : (
        <div className="rounded-xl border border-dashed border-border bg-background p-3">
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Camera className="size-3.5" />
            <span className="text-xs">No food photos for today — anything below is fully manual.</span>
          </div>
        </div>
      )}

      {signalIsLive && <div className="h-px bg-border" />}

      <div className="space-y-2">
        <p className="text-xs text-muted-foreground">
          {hasPhotos ? 'Add anything else you ate or drank' : 'Add anything you ate or drank'}
        </p>
        {manualOptions.length > 0 && (
          <div className="grid grid-cols-2 gap-2">
            {manualOptions.map((opt) => {
              const selected = selectedFlags.includes(opt.id)
              return (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => onToggle(opt.id)}
                  className={[
                    'min-h-[48px] rounded-xl border px-2 py-2.5 text-sm font-medium transition-all',
                    selected
                      ? 'border-primary bg-primary text-primary-foreground shadow-sm'
                      : 'border-border bg-background text-muted-foreground',
                  ].join(' ')}
                >
                  {opt.label}
                </button>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

interface AutosaveFns {
  flush: () => void
  forceFlush: () => Promise<void>
  retry: () => void
  flushBeacon: () => void
}

interface CheckinFormProps {
  date: string
  existingEntry?: Entry | null
  /** Called whenever the pill status changes (status, lastSavedAt, errorMessage). */
  onAutosaveStateChange?: (state: AutosaveState) => void
  /**
   * Called once on mount with stable flush/forceFlush/retry refs.
   * The parent stores these in refs — no state, no re-render.
   */
  onAutosaveFnsReady?: (fns: AutosaveFns) => void
}

export function CheckinForm({ date, existingEntry, onAutosaveStateChange, onAutosaveFnsReady }: CheckinFormProps) {
  const deletePhotoMutation = useDeletePhoto()
  const queryClient = useQueryClient()
  const { data: catalog } = useSupplementCatalog(false)
  const { data: activeTreatments } = useTreatments(date)

  const defaultSupplements = (catalog ?? [])
    .filter((c) => !c.archived)
    .map((c) => c.key)
    .join(',')

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

  // isDirty: true once the user has made a real change. Prevents autosave from
  // firing during the hydration effect or the supplements pre-fill effect.
  // We use both a ref (for synchronous reads) and state (to trigger re-renders
  // so the autosave hook sees the updated `enabled` flag).
  const dirtyRef = useRef(false)
  const [isDirty, setIsDirty] = useState(false)
  const markDirty = useCallback(() => {
    if (!dirtyRef.current) {
      dirtyRef.current = true
      setIsDirty(true)
    }
  }, [])

  // Wrappers that mark dirty before updating state.
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

  // When creating a new entry, pre-fill supplements with the current active catalog.
  // This does NOT mark dirty — it's an initialization, not a user change.
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
      } else if (existingEntry.stool_normal === true) {
        setStoolStatus('normal')
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

  const handleDietToggle = (id: string) => {
    markDirty()
    const current = dietRisk ? dietRisk.split(',').filter(Boolean) : []
    if (current.includes(id)) {
      setDietRisk(current.filter((d) => d !== id).join(','))
    } else {
      setDietRisk([...current, id].join(','))
    }
  }

  const handleDeleteExistingPhoto = async (photoId: number) => {
    try {
      await deletePhotoMutation.mutateAsync(photoId)
      setExistingPhotos((prev) => prev.filter((p) => p.id !== photoId))
      queryClient.invalidateQueries({ queryKey: ['entry', date] })
      toast.success('Photo deleted')
    } catch {
      toast.error('Failed to delete photo')
    }
  }

  // Bristol gate: user must pick a Bristol type before autosave is enabled.
  const bristolBlocked = stoolStatus === 'abnormal' && bristolType === null

  // Memoized payload — only recomputes when scalar values change.
  // entry_time is omitted from the payload to avoid thrashing the column on every save;
  // the first POST sets it, subsequent PUTs let the backend use updated_at.
  const payload = useMemo<EntryCreate>(() => ({
    date,
    schema_version: 2,
    overall,
    bloating,
    stool_status: stoolStatus,
    bristol_type:
      stoolStatus === 'abnormal' && bristolType !== null ? bristolType : undefined,
    joint_pain: jointPain,
    neuro,
    sleep_quality: sleepQuality,
    stress,
    diet_risk: dietRisk,
    supplements,
    sick,
    hot_shower: hotShower,
    // Always send notes (even when empty) — see memory: form payload patterns.
    notes,
    alcohol_units: alcoholUnits,
    caffeine_servings: caffeineServings,
    symptoms_json: symptomsJson,
  }), [
    date, overall, bloating, stoolStatus, bristolType, jointPain, neuro,
    sleepQuality, stress, dietRisk, supplements, sick, hotShower, notes,
    alcoholUnits, caffeineServings, symptomsJson,
  ])

  const autosave = useAutosaveEntry({
    date,
    payload,
    enabled: !bristolBlocked && isDirty,
    blocked: bristolBlocked,
    hasExistingEntry: !!existingEntry,
  })

  // Surface plain serializable state to parent pill — only re-runs when
  // status/lastSavedAt/errorMessage change. flush/forceFlush/retry are
  // registered once via onAutosaveFnsReady below to break the re-render cycle.
  useEffect(() => {
    onAutosaveStateChange?.({
      status: autosave.status,
      lastSavedAt: autosave.lastSavedAt,
      errorMessage: autosave.errorMessage,
    })
  }, [autosave.status, autosave.lastSavedAt, autosave.errorMessage, onAutosaveStateChange])

  // Register flush/forceFlush/retry refs with parent once on mount.
  // These are stored as refs in the parent — no setState, no re-render cycle.
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

  // Flush autosave on blur of the notes field (and any text input).
  const handleBlur = useCallback(() => {
    autosave.flush()
  }, [autosave])

  return (
    <div className="space-y-7 pb-8">
      {activeTreatments && activeTreatments.length > 0 && (
        <Link
          href="/treatments"
          className="flex items-center gap-2 rounded-xl border border-border bg-muted/50 px-4 py-3 transition-colors hover:bg-muted"
        >
          <Pill className="size-4 shrink-0 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            <span className="font-medium text-foreground">Active treatments: </span>
            {activeTreatments.map((t) => {
              const start = new Date(t.start_date + 'T00:00:00')
              const current = new Date(date + 'T00:00:00')
              const dayNum = Math.floor((current.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)) + 1
              return `${t.name} (day ${dayNum})`
            }).join(', ')}
          </p>
        </Link>
      )}

      <ScaleInput
        label="How was your day?"
        value={overall}
        onChange={(v) => setOverallDirty(v as number)}
        options={[
          { value: 1, label: 'Very Poor' },
          { value: 2, label: 'Standard' },
          { value: 3, label: 'Very Good' },
        ]}
      />

      <ScaleInput
        label="Bloating"
        value={bloating}
        onChange={(v) => setBloatingDirty(v as number)}
        options={[
          { value: 0, label: 'None' },
          { value: 1, label: 'Mild' },
          { value: 2, label: 'Moderate' },
          { value: 3, label: 'Severe' },
        ]}
      />

      <div className="space-y-3">
        <ScaleInput
          label="Stool"
          value={stoolStatus}
          onChange={(v) => setStoolStatusDirty(v as StoolStatus)}
          options={[
            { value: 'normal', label: 'Normal' },
            { value: 'abnormal', label: 'Abnormal' },
            { value: 'none', label: 'No movement' },
          ]}
        />
        {stoolStatus === 'abnormal' && (
          <>
            <BristolInput value={bristolType} onChange={setBristolTypeDirty} />
            {bristolBlocked && (
              <p className="text-xs text-amber-600 dark:text-amber-400">
                Pick a Bristol type to keep saving
              </p>
            )}
          </>
        )}
      </div>

      <ScaleInput
        label="Joint pain / crepitus"
        value={jointPain}
        onChange={(v) => setJointPainDirty(v as number)}
        options={[
          { value: 0, label: 'None' },
          { value: 1, label: 'Mild' },
          { value: 2, label: 'Moderate' },
          { value: 3, label: 'Severe' },
        ]}
      />

      <ScaleInput
        label="Neuro symptoms"
        value={neuro}
        onChange={(v) => setNeuroDirty(v as number)}
        options={[
          { value: -1, label: 'Worse' },
          { value: 0, label: 'Baseline' },
          { value: 1, label: 'Better' },
        ]}
      />

      <ScaleInput
        label="Sleep quality (last night)"
        value={sleepQuality}
        onChange={(v) => setSleepQualityDirty(v as number)}
        options={[
          { value: 1, label: 'Poor' },
          { value: 2, label: 'OK' },
          { value: 3, label: 'Good' },
        ]}
      />

      <ScaleInput
        label="Stress level"
        value={stress}
        onChange={(v) => setStressDirty(v as number)}
        options={[
          { value: 1, label: 'Low' },
          { value: 2, label: 'Medium' },
          { value: 3, label: 'High' },
        ]}
      />

      <DietRiskSection
        existingEntry={existingEntry}
        existingPhotos={existingPhotos}
        dietRisk={dietRisk}
        onToggle={handleDietToggle}
      />

      <SupplementPicker
        value={supplements}
        onChange={(v) => {
          markDirty()
          setSupplements(v)
          setSupplementsTouched(true)
        }}
      />

      <SymptomPicker value={symptomsJson} onChange={setSymptomsJsonDirty} />

      <div className="space-y-2">
        <label className="text-sm font-semibold">Alcohol & Caffeine</label>
        <div className="flex justify-around rounded-xl border border-border bg-background p-4">
          <Stepper
            value={alcoholUnits}
            onChange={setAlcoholUnitsDirty}
            min={0}
            max={10}
            label="Alcohol units"
            tooltip="1 unit = small glass of wine / half a beer"
          />
          <Stepper
            value={caffeineServings}
            onChange={setCaffeineServingsDirty}
            min={0}
            max={10}
            label="Caffeine servings"
            tooltip="1 serving = one coffee / one strong tea"
          />
        </div>
      </div>

      <BinaryInput
        label="Sick / cold?"
        value={sick}
        onChange={setSickDirty}
        trueLabel="Yes"
        falseLabel="No"
      />

      <BinaryInput
        label="Full-body hot shower today?"
        value={hotShower}
        onChange={setHotShowerDirty}
        trueLabel="Yes"
        falseLabel="No"
      />

      <NotesInput value={notes} onChange={setNotesDirty} onBlur={handleBlur} />

      {existingPhotos.length > 0 && (
        <div className="space-y-3">
          <label className="text-sm font-semibold">Uploaded photos</label>
          <div className="grid grid-cols-2 gap-3">
            {existingPhotos.map((photo) => (
              <div key={photo.id}>
                <div className="relative rounded-xl border border-border overflow-hidden">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={`/api/v1/photos/${photo.id}/file`}
                    alt={photo.label || 'Photo'}
                    className="aspect-square w-full object-cover"
                  />
                  {photo.label && (
                    <div className="px-2 py-1.5 text-xs text-muted-foreground truncate">
                      {photo.label}
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={() => handleDeleteExistingPhoto(photo.id)}
                    className="absolute right-1.5 top-1.5 flex size-7 items-center justify-center rounded-full bg-black/60 text-white transition-colors hover:bg-black/80"
                  >
                    <X className="size-4" />
                  </button>
                </div>
                <PhotoAnalysis photoId={photo.id} />
              </div>
            ))}
          </div>
        </div>
      )}

      <PhotoCapture
        date={date}
        ensureEntryExists={autosave.forceFlush}
        onEntryEnsured={markDirty}
      />
    </div>
  )
}
