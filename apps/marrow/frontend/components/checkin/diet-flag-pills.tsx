import { dietFlagClass, dietFlagFallback, statusPill } from '@/lib/ui/status'

// Renders aggregated diet-risk flag strings (the FLAG_VOCAB from the backend:
// high-histamine / high-fodmap / gluten / dairy) as compact colored pills.
// Presentational leaf — no 'use client' needed. Colors match the per-ingredient
// DietaryBadges language via lib/ui/status.

export function DietFlagPills({ flags }: { flags: string[] }) {
  if (!flags || flags.length === 0) return null
  return (
    <span className="inline-flex flex-wrap gap-0.5">
      {flags.map((flag) => {
        const style = dietFlagClass[flag] ?? {
          label: flag,
          className: dietFlagFallback.className || statusPill.muted,
        }
        return (
          <span
            key={flag}
            className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-none ${style.className}`}
          >
            {style.label || flag}
          </span>
        )
      })}
    </span>
  )
}
