'use client'

import { Eye } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@f0rge/ui'
import { handleMutationError } from '@f0rge/ui/api'
import { ScaleInput } from '@/components/checkin/scale-input'
import { useDietTagCatalog } from '@/lib/api/hooks/catalogs'
import { useUpdateProfileTagFilter, useUserSettings } from '@/lib/api/hooks/settings'
import type { ProfileTagFilterMode } from '@/lib/api/types/settings'
import { SettingsCard } from './settings-card'

const MODE_OPTIONS = [
  { value: 'off' as const, label: 'Off' },
  { value: 'hide' as const, label: 'Hide' },
  { value: 'show_only' as const, label: 'Show only' },
]

export function ProfileVisibilitySection() {
  const settings = useUserSettings()
  const catalog = useDietTagCatalog()
  const updateFilter = useUpdateProfileTagFilter()

  const mode = settings.data?.profile_tag_filter_mode ?? 'off'
  const selected = settings.data?.profile_filter_tags ?? []
  const tags = catalog.data ?? []
  const disabled = mode === 'off'

  const persist = async (nextMode: ProfileTagFilterMode, nextTags: string[]) => {
    try {
      await updateFilter.mutateAsync({
        profile_tag_filter_mode: nextMode,
        profile_filter_tags: nextTags,
      })
      toast.success('Profile visibility saved')
    } catch (err) {
      handleMutationError(err, 'Could not save profile visibility')
    }
  }

  const handleModeChange = (value: number | string) => {
    const next = value as ProfileTagFilterMode
    if (next === mode) return
    // Show only with no tags matches nothing; the server treats that as off.
    // Persist anyway so the control doesn't dead-click — just say why.
    if (next === 'show_only' && selected.length === 0) {
      toast.info('Pick at least one tag for "Show only" to filter anything.')
    }
    void persist(next, selected)
  }

  const toggleTag = (key: string) => {
    const next = selected.includes(key)
      ? selected.filter((k) => k !== key)
      : [...selected, key]
    void persist(mode, next)
  }

  return (
    <SettingsCard icon={Eye} iconClassName="text-violet-500" title="Profile visibility">
      <p className="text-sm text-muted-foreground">
        Automatically filter your profile meal grids by diet tag. Hide removes matching meals;
        Show only keeps nothing but matches. Check-ins always show every meal.
      </p>
      <ScaleInput
        label="Rule"
        description="Applies to both My meals and Shared with me."
        options={MODE_OPTIONS}
        value={mode}
        onChange={handleModeChange}
      />
      <div className={cn(disabled && 'opacity-50')}>
        <p className="text-sm font-semibold">Tags</p>
        {tags.length === 0 ? (
          <p className="mt-1 text-xs text-muted-foreground">No diet tags in your catalog yet.</p>
        ) : (
          <div className="mt-1">
            {tags.map((tag) => (
              <label key={tag.key} className="flex cursor-pointer items-center gap-3 py-1.5">
                <input
                  type="checkbox"
                  checked={selected.includes(tag.key)}
                  onChange={() => toggleTag(tag.key)}
                  disabled={disabled || updateFilter.isPending}
                  className="size-4 shrink-0 accent-primary"
                />
                <span className="text-sm">{tag.label}</span>
              </label>
            ))}
          </div>
        )}
      </div>
    </SettingsCard>
  )
}
