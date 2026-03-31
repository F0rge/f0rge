'use client'

import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { Loader2, X } from 'lucide-react'
import { ScaleInput } from './scale-input'
import { BinaryInput } from './binary-input'
import { NotesInput } from './notes-input'
import { PhotoCapture } from './photo-capture'
import { useQueryClient } from '@tanstack/react-query'
import { useCreateEntry, useUpdateEntry, useUploadPhoto, useDeletePhoto } from '@/lib/api/hooks'
import { apiDelete } from '@/lib/api/client'
import type { Entry, EntryCreate } from '@/lib/api/types'

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

  const [overall, setOverall] = useState(2)
  const [bloating, setBloating] = useState(0)
  const [stoolNormal, setStoolNormal] = useState(true)
  const [stoolType, setStoolType] = useState<string>('')
  const [jointPain, setJointPain] = useState(0)
  const [neuro, setNeuro] = useState(0)
  const [sleepQuality, setSleepQuality] = useState(2)
  const [stress, setStress] = useState(1)
  const [dietRisk, setDietRisk] = useState<string>('normal')
  const [supplements, setSupplements] = useState<string>('nac,fish_oil,magnesium,beef_organs,allicin,oregano,vitamin_d_k2,dao,creatine')
  const [sick, setSick] = useState(false)
  const [notes, setNotes] = useState('')
  const [photos, setPhotos] = useState<File[]>([])
  const [labels, setLabels] = useState<string[]>([])
  const [existingPhotos, setExistingPhotos] = useState<Entry['photos']>([])
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (existingEntry) {
      setOverall(existingEntry.overall)
      setBloating(existingEntry.bloating)
      setStoolNormal(existingEntry.stool_normal)
      setStoolType(existingEntry.stool_type || '')
      setJointPain(existingEntry.joint_pain)
      setNeuro(existingEntry.neuro)
      setSleepQuality(existingEntry.sleep_quality)
      setStress(existingEntry.stress)
      setDietRisk(existingEntry.diet_risk)
      setSupplements(existingEntry.supplements)
      setSick(existingEntry.sick)
      setNotes(existingEntry.notes || '')
      setExistingPhotos(existingEntry.photos || [])
    }
  }, [existingEntry])

  // Reset stool type when switching back to normal
  useEffect(() => {
    if (stoolNormal) setStoolType('')
  }, [stoolNormal])

  const handleDietToggle = (id: string) => {
    const current = dietRisk ? dietRisk.split(',').filter(Boolean) : []

    if (id === 'normal') {
      setDietRisk('normal')
      return
    }

    // Remove 'normal' when selecting a risk
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
    setSubmitting(true)
    try {
      const data: EntryCreate = {
        date,
        overall,
        bloating,
        stool_normal: stoolNormal,
        stool_type: stoolNormal ? undefined : stoolType || undefined,
        joint_pain: jointPain,
        neuro,
        sleep_quality: sleepQuality,
        stress,
        diet_risk: dietRisk,
        supplements,
        sick,
        notes: notes || undefined,
      }

      if (existingEntry) {
        await updateEntry.mutateAsync({ date, data })
      } else {
        await createEntry.mutateAsync(data)
      }

      // Upload photos one by one
      for (let i = 0; i < photos.length; i++) {
        await uploadPhoto.mutateAsync({
          date,
          file: photos[i],
          label: labels[i] || undefined,
        })
      }

      toast.success(existingEntry ? 'Entry updated' : 'Entry saved')
      setPhotos([])
      setLabels([])
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
        <BinaryInput
          label="Stool"
          value={stoolNormal}
          onChange={setStoolNormal}
          trueLabel="Normal"
          falseLabel="Abnormal"
        />
        {!stoolNormal && (
          <ScaleInput
            label="Type"
            value={stoolType}
            onChange={(v) => setStoolType(v as string)}
            options={[
              { value: 'soft', label: 'Soft / Loose' },
              { value: 'constipated', label: 'Constipated' },
            ]}
          />
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

      {/* Diet risk - multi-select */}
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

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <label className="text-sm font-semibold">Supplements taken</label>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => setSupplements('nac,fish_oil,magnesium,beef_organs,allicin,oregano,vitamin_d_k2,dao,creatine')}
              className="text-xs text-muted-foreground underline"
            >
              All
            </button>
            <button
              type="button"
              onClick={() => setSupplements('')}
              className="text-xs text-muted-foreground underline"
            >
              None
            </button>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-2">
          {[
            { id: 'nac', label: 'NAC' },
            { id: 'fish_oil', label: 'Fish Oil' },
            { id: 'magnesium', label: 'Magnesium' },
            { id: 'beef_organs', label: 'Beef Organs' },
            { id: 'allicin', label: 'Allicin' },
            { id: 'oregano', label: 'Oregano Oil' },
            { id: 'vitamin_d_k2', label: 'D3 + K2' },
            { id: 'dao', label: 'DAO' },
            { id: 'creatine', label: 'Creatine' },
          ].map((supp) => {
            const taken = supplements.split(',').includes(supp.id)
            return (
              <button
                key={supp.id}
                type="button"
                onClick={() => {
                  const current = supplements ? supplements.split(',').filter(Boolean) : []
                  const updated = taken
                    ? current.filter((s) => s !== supp.id)
                    : [...current, supp.id]
                  setSupplements(updated.join(','))
                }}
                className={`min-h-[48px] rounded-xl border px-2 py-2.5 text-sm font-medium transition-all ${
                  taken
                    ? 'border-primary bg-primary text-primary-foreground shadow-sm'
                    : 'border-border bg-background text-muted-foreground'
                }`}
              >
                {supp.label}
              </button>
            )
          })}
        </div>
      </div>

      <BinaryInput
        label="Sick / cold?"
        value={sick}
        onChange={setSick}
        trueLabel="Yes"
        falseLabel="No"
      />

      <NotesInput value={notes} onChange={setNotes} />

      {/* Existing photos with delete */}
      {existingPhotos.length > 0 && (
        <div className="space-y-3">
          <label className="text-sm font-semibold">Uploaded photos</label>
          <div className="grid grid-cols-2 gap-3">
            {existingPhotos.map((photo) => (
              <div key={photo.id} className="relative rounded-xl border border-border overflow-hidden">
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
            ))}
          </div>
        </div>
      )}

      <PhotoCapture
        photos={photos}
        labels={labels}
        onPhotosChange={setPhotos}
        onLabelsChange={setLabels}
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
