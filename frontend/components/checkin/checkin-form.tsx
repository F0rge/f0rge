'use client'

import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { Loader2 } from 'lucide-react'
import { ScaleInput } from './scale-input'
import { BinaryInput } from './binary-input'
import { NotesInput } from './notes-input'
import { PhotoCapture } from './photo-capture'
import { useCreateEntry, useUpdateEntry, useUploadPhoto } from '@/lib/api/hooks'
import type { Entry, EntryCreate } from '@/lib/api/types'

interface CheckinFormProps {
  date: string
  existingEntry?: Entry | null
  onSuccess?: () => void
}

export function CheckinForm({ date, existingEntry, onSuccess }: CheckinFormProps) {
  const createEntry = useCreateEntry()
  const updateEntry = useUpdateEntry()
  const uploadPhoto = useUploadPhoto()

  const [overall, setOverall] = useState(3)
  const [bloating, setBloating] = useState(0)
  const [stoolNormal, setStoolNormal] = useState(true)
  const [jointPain, setJointPain] = useState(0)
  const [neuro, setNeuro] = useState(0)
  const [sleepQuality, setSleepQuality] = useState(2)
  const [stress, setStress] = useState(1)
  const [dietRisk, setDietRisk] = useState<string>('normal')
  const [supplements, setSupplements] = useState<string>('yes')
  const [sick, setSick] = useState(false)
  const [notes, setNotes] = useState('')
  const [photos, setPhotos] = useState<File[]>([])
  const [labels, setLabels] = useState<string[]>([])
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (existingEntry) {
      setOverall(existingEntry.overall)
      setBloating(existingEntry.bloating)
      setStoolNormal(existingEntry.stool_normal)
      setJointPain(existingEntry.joint_pain)
      setNeuro(existingEntry.neuro)
      setSleepQuality(existingEntry.sleep_quality)
      setStress(existingEntry.stress)
      setDietRisk(existingEntry.diet_risk)
      setSupplements(existingEntry.supplements)
      setSick(existingEntry.sick)
      setNotes(existingEntry.notes || '')
    }
  }, [existingEntry])

  const handleSubmit = async () => {
    setSubmitting(true)
    try {
      const data: EntryCreate = {
        date,
        overall,
        bloating,
        stool_normal: stoolNormal,
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
      onSuccess?.()
    } catch {
      toast.error('Failed to save entry')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-6 pb-8">
      <ScaleInput
        label="How was your day?"
        value={overall}
        onChange={(v) => setOverall(v as number)}
        options={[
          { value: 1, label: 'Very Poor' },
          { value: 2, label: 'Poor' },
          { value: 3, label: 'Standard' },
          { value: 4, label: 'Good' },
          { value: 5, label: 'Very Good' },
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

      <BinaryInput
        label="Stool"
        value={stoolNormal}
        onChange={setStoolNormal}
        trueLabel="Normal"
        falseLabel="Abnormal"
      />

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

      <ScaleInput
        label="Diet risk"
        value={dietRisk}
        onChange={(v) => setDietRisk(v as string)}
        options={[
          { value: 'normal', label: 'Normal' },
          { value: 'high-histamine', label: 'High-histamine' },
          { value: 'high-fodmap', label: 'High-FODMAP' },
          { value: 'both', label: 'Both' },
        ]}
      />

      <ScaleInput
        label="Supplements taken"
        value={supplements}
        onChange={(v) => setSupplements(v as string)}
        options={[
          { value: 'yes', label: 'Yes' },
          { value: 'partial', label: 'Partial' },
          { value: 'no', label: 'No' },
        ]}
      />

      <BinaryInput
        label="Sick / cold?"
        value={sick}
        onChange={setSick}
        trueLabel="Yes"
        falseLabel="No"
      />

      <NotesInput value={notes} onChange={setNotes} />

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
        className="flex min-h-[48px] w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
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
