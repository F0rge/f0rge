'use client'

import { cn } from '@f0rge/ui'
import { handleMutationError } from '@f0rge/ui/api'
import { useDietTagCatalog } from '@/lib/api/hooks/catalogs'
import { useUpdatePhotoDietTags } from '@/lib/api/hooks/entries'
import type { Photo } from '@/lib/api/types'

interface PhotoDietTagsSectionProps {
  photo: Photo
}

/**
 * Diet tags for one photo. The user's non-archived catalog tags render as
 * toggle chips reflecting the photo's explicit tag set (each toggle PATCHes
 * the full replacement array). Derived tags come from the confirmed analysis
 * and are display-only, marked "auto".
 */
export function PhotoDietTagsSection({ photo }: PhotoDietTagsSectionProps) {
  const catalog = useDietTagCatalog()
  const updateTags = useUpdatePhotoDietTags()

  // Derived from props, not mirrored into state: the mutation invalidates
  // ['photos']/['entry'] and the chips re-render from the refetch. Mirroring
  // needs a setState-in-effect, which react-hooks/set-state-in-effect rejects.
  const explicit = photo.diet_tags ?? []
  const derived = photo.derived_diet_tags ?? []
  const items = catalog.data ?? []
  const labelFor = (key: string) => items.find((t) => t.key === key)?.label ?? key

  const toggle = async (key: string) => {
    const next = explicit.includes(key)
      ? explicit.filter((k) => k !== key)
      : [...explicit, key]
    try {
      await updateTags.mutateAsync({ photoId: photo.id, dietTags: next })
    } catch (err) {
      handleMutationError(err, 'Could not update diet tags')
    }
  }

  if (items.length === 0 && derived.length === 0) return null

  return (
    <div className="mb-3 space-y-2 rounded-lg border border-border bg-muted/30 p-3">
      <p className="text-xs font-medium text-muted-foreground">Diet tags</p>
      <div className="flex flex-wrap gap-1.5">
        {items.map((tag) => {
          const active = explicit.includes(tag.key)
          return (
            <button
              key={tag.key}
              type="button"
              onClick={() => void toggle(tag.key)}
              disabled={updateTags.isPending}
              aria-pressed={active}
              className={cn(
                'rounded-full border px-2.5 py-1 text-xs font-medium transition-colors disabled:opacity-50',
                active
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'border-border bg-background text-muted-foreground hover:text-foreground',
              )}
            >
              {tag.label}
            </button>
          )
        })}
        {derived.map((key) => (
          <span
            key={`derived-${key}`}
            className="inline-flex items-center gap-1 rounded-full border border-dashed border-border bg-muted px-2.5 py-1 text-xs text-muted-foreground"
          >
            {labelFor(key)}
            <span className="text-[10px] uppercase tracking-wide">auto</span>
          </span>
        ))}
      </div>
    </div>
  )
}
