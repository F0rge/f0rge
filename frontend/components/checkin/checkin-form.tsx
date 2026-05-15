'use client'

import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import Link from 'next/link'
import { Loader2, Pill, X } from 'lucide-react'
import { ScaleInput } from './scale-input'
import { BinaryInput } from './binary-input'
import { BristolInput } from './bristol-input'
import { NotesInput } from './notes-input'
import { PhotoCapture } from './photo-capture'
import { SupplementPicker } from './supplement-picker'
import { SymptomPicker } from './symptom-picker'
import { Stepper } from '@/components/ui/stepper'
import { useQueryClient } from '@tanstack/react-query'
import {
  useCreateEntry,
  useUpdateEntry,
  useUploadPhoto,
  useDeletePhoto,
  useSupplementCatalog,
  useTreatments,
} from '@/lib/api/hooks'
import { apiGet, apiPut } from '@/lib/api/client'
import { PhotoAnalysis } from './photo-analysis'
import type { Entry, EntryCreate, StoolStatus } from '@/lib/api/types'

const DIET_OPTIONS = [
  { id: 'normal', label: 'Normal' },
  { id: 'high-histamine', label: 'High-histamine' },
  { id: 'high-fodmap', label: 'High-FODMAP' },
  { id: 'gluten', label: 'Gluten' },
  { id: 'not-sure', label: 'Not sure' },
]

interface CheckinFormProps {
  date: string
  existingEntry?: Entry | null
  onSuccess?: () => void
}

export function CheckinForm({ date, existingEntry, onSuccess }: CheckinFormProps) {
  const createEntry = useCreateEntry()
  const updateEntry = useUpdateEntry()
  const uploadPhoto = useUploadPhoto()
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
  const [dietRisk, setDietRisk] = useState<string>('normal')
  const [supplements, setSupplements] = useState<string>('')
  const [supplementsTouched, setSupplementsTouched] = useState(false)
  const [symptomsJson, setSymptomsJson] = useState<Record<string, number>>({})
  const [sick, setSick] = useState(false)
  const [hotShower, setHotShower] = useState(false)
  const [notes, setNotes] = useState('')
  const [photos, setPhotos] = useState<File[]>([])
  const [labels, setLabels] = useState<string[]>([])
  const [mealTimes, setMealTimes] = useState<(Date | null)[]>([])
  const [existingPhotos, setExistingPhotos] = useState<Entry['photos']>([])
  const [alcoholUnits, setAlcoholUnits] = useState(0)
  const [caffeineServings, setCaffeineServings] = useState(0)
  const [submitting, setSubmitting] = useState(false)

  // When creating a new entry, pre-fill supplements with the current active catalog.
  useEffect(() => {
    if (!existingEntry && !supplementsTouched && defaultSupplements) {
      setSupplements(defaultSupplements)
    }
  }, [defaultSupplements, existingEntry, supplementsTouched])

  useEffect(() => {
    if (existingEntry) {
      setOverall(existingEntry.overall)
      setBloating(existingEntry.bloating)
      // Map v1 entries onto the v2 stool fields.
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
      setDietRisk(existingEntry.diet_risk)
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
    const current = dietRisk ? dietRisk.split(',').filter(Boolean) : []

    if (id === 'normal') {
      setDietRisk('normal')
      return
    }

    const withoutNormal = current.filter((d) => d !== 'normal')

    if (withoutNormal.includes(id)) {
      const updated = withoutNormal.filter((d) => d !== id)
      setDietRisk(updated.length === 0 ? 'normal' : updated.join(','))
    } else {
      setDietRisk([...withoutNormal, id].join(','))
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

  const handleSubmit = async () => {
    if (stoolStatus === 'abnormal' && bristolType === null) {
      toast.error('Pick a Bristol type, or switch stool back to Normal / None')
      return
    }
    setSubmitting(true)
    try {
      const data: EntryCreate = {
        date,
        schema_version: 2,
        entry_time: new Date().toISOString(),
        overall,
        bloating,
        stool_status: stoolStatus,
        bristol_type:
          stoolStatus === 'abnormal' && bristolType !== null
            ? bristolType
            : undefined,
        joint_pain: jointPain,
        neuro,
        sleep_quality: sleepQuality,
        stress,
        diet_risk: dietRisk,
        supplements,
        sick,
        hot_shower: hotShower,
        notes: notes || undefined,
        alcohol_units: alcoholUnits,
        caffeine_servings: caffeineServings,
        symptoms_json: symptomsJson,
      }

      if (existingEntry) {
        await updateEntry.mutateAsync({ date, data })
      } else {
        await createEntry.mutateAsync(data)
      }

      for (let i = 0; i < photos.length; i++) {
        await uploadPhoto.mutateAsync({
          date,
          file: photos[i],
          label: labels[i] || undefined,
          mealTime: mealTimes[i] ?? undefined,
        })
      }

      // Auto-confirm pending analyses
      for (const photo of existingPhotos) {
        try {
          const analysis = await apiGet(`/photos/${photo.id}/analysis`)
          if (analysis && analysis.status === 'complete') {
            await apiPut(`/photos/${photo.id}/analysis/confirm`, {})
          }
        } catch {
          // Ignore — analysis might not exist
        }
      }

      toast.success(existingEntry ? 'Entry updated' : 'Entry saved')
      setPhotos([])
      setLabels([])
      setMealTimes([])
      queryClient.invalidateQueries({ queryKey: ['entry', date] })
      onSuccess?.()
    } catch {
      toast.error('Failed to save entry')
    } finally {
      setSubmitting(false)
    }
  }

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
        onChange={(v) => setOverall(v as number)}
        options={[
          { value: 1, label: 'Very Poor' },
          { value: 2, label: 'Standard' },
          { value: 3, label: 'Very Good' },
        ]}
      />

      <ScaleInput
        label="Bloating"
        value={bloating}
        onChange={(v) => setBloating(v as number)}
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
          onChange={(v) => setStoolStatus(v as StoolStatus)}
          options={[
            { value: 'normal', label: 'Normal' },
            { value: 'abnormal', label: 'Abnormal' },
            { value: 'none', label: 'No movement' },
          ]}
        />
        {stoolStatus === 'abnormal' && (
          <BristolInput value={bristolType} onChange={setBristolType} />
        )}
      </div>

      <ScaleInput
        label="Joint pain / crepitus"
        value={jointPain}
        onChange={(v) => setJointPain(v as number)}
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
        onChange={(v) => setNeuro(v as number)}
        options={[
          { value: -1, label: 'Worse' },
          { value: 0, label: 'Baseline' },
          { value: 1, label: 'Better' },
        ]}
      />

      <ScaleInput
        label="Sleep quality (last night)"
        value={sleepQuality}
        onChange={(v) => setSleepQuality(v as number)}
        options={[
          { value: 1, label: 'Poor' },
          { value: 2, label: 'OK' },
          { value: 3, label: 'Good' },
        ]}
      />

      <ScaleInput
        label="Stress level"
        value={stress}
        onChange={(v) => setStress(v as number)}
        options={[
          { value: 1, label: 'Low' },
          { value: 2, label: 'Medium' },
          { value: 3, label: 'High' },
        ]}
      />

      <div className="space-y-3">
        <label className="text-sm font-semibold">Diet risk</label>
        <div className="grid grid-cols-3 gap-2">
          {DIET_OPTIONS.map((opt) => {
            const selected = dietRisk.split(',').includes(opt.id)
            return (
              <button
                key={opt.id}
                type="button"
                onClick={() => handleDietToggle(opt.id)}
                className={`min-h-[48px] rounded-xl border px-2 py-2.5 text-sm font-medium transition-all ${
                  selected
                    ? 'border-primary bg-primary text-primary-foreground shadow-sm'
                    : 'border-border bg-background text-muted-foreground'
                }`}
              >
                {opt.label}
              </button>
            )
          })}
        </div>
      </div>

      <SupplementPicker
        value={supplements}
        onChange={(v) => {
          setSupplements(v)
          setSupplementsTouched(true)
        }}
      />

      <SymptomPicker value={symptomsJson} onChange={setSymptomsJson} />

      <div className="space-y-2">
        <label className="text-sm font-semibold">Alcohol & Caffeine</label>
        <div className="flex justify-around rounded-xl border border-border bg-background p-4">
          <Stepper
            value={alcoholUnits}
            onChange={setAlcoholUnits}
            min={0}
            max={10}
            label="Alcohol units"
            tooltip="1 unit = small glass of wine / half a beer"
          />
          <Stepper
            value={caffeineServings}
            onChange={setCaffeineServings}
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
        onChange={setSick}
        trueLabel="Yes"
        falseLabel="No"
      />

      <BinaryInput
        label="Full-body hot shower today?"
        value={hotShower}
        onChange={setHotShower}
        trueLabel="Yes"
        falseLabel="No"
      />

      <NotesInput value={notes} onChange={setNotes} />

      {existingPhotos.length > 0 && (
        <div className="space-y-3">
          <label className="text-sm font-semibold">Uploaded photos</label>
          <div className="grid grid-cols-2 gap-3">
            {existingPhotos.map((photo) => (
              <div key={photo.id}>
                <div className="relative rounded-xl border border-border overflow-hidden">
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
        photos={photos}
        labels={labels}
        mealTimes={mealTimes}
        onPhotosChange={setPhotos}
        onLabelsChange={setLabels}
        onMealTimesChange={setMealTimes}
      />

      <button
        type="button"
        onClick={handleSubmit}
        disabled={submitting}
        className="flex min-h-[52px] w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3.5 text-base font-semibold text-primary-foreground transition-all hover:bg-primary/90 disabled:opacity-50 shadow-sm"
      >
        {submitting ? (
          <>
            <Loader2 className="size-4 animate-spin" />
            Saving...
          </>
        ) : existingEntry ? (
          'Update Entry'
        ) : (
          'Save Entry'
        )}
      </button>
    </div>
  )
}
