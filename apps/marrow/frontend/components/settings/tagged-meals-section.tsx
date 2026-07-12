'use client'

import { Tag } from 'lucide-react'
import { toast } from 'sonner'
import { ScaleInput } from '@/components/checkin/scale-input'
import { useUpdateTaggedMealMode, useUserSettings } from '@/lib/api/hooks/settings'
import { handleMutationError } from '@f0rge/ui/api'
import type { TaggedMealMode } from '@/lib/api/types/settings'
import { SettingsCard } from './settings-card'

const MODE_OPTIONS = [
  { value: 'approve' as const, label: 'Approve' },
  { value: 'auto' as const, label: 'Auto' },
]

export function TaggedMealsSection() {
  const settings = useUserSettings()
  const updateMode = useUpdateTaggedMealMode()

  const mode = settings.data?.tagged_meal_mode ?? 'approve'

  const handleChange = async (value: number | string) => {
    const next = value as TaggedMealMode
    if (next === mode) return
    try {
      await updateMode.mutateAsync({ tagged_meal_mode: next })
      toast.success('Tagged meal preference saved')
    } catch (err) {
      handleMutationError(err, 'Could not save preference')
    }
  }

  return (
    <SettingsCard icon={Tag} iconClassName="text-sky-500" title="Tagged meals">
      <p className="text-sm text-muted-foreground">
        When someone tags you on a meal, choose whether it lands on your timeline automatically or
        waits for your approval.
      </p>
      <ScaleInput
        label="Delivery"
        description="Auto adds tagged meals after their analysis is confirmed. Approve lets you review first."
        options={MODE_OPTIONS}
        value={mode}
        onChange={handleChange}
      />
    </SettingsCard>
  )
}
