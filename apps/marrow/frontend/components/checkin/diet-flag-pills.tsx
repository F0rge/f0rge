// Renders aggregated diet-risk flag strings (the FLAG_VOCAB from the backend:
// high-histamine / high-fodmap / gluten / dairy) as compact colored pills.
// Presentational leaf — no 'use client' needed. Colors match the per-ingredient
// DietaryBadges language (gluten=red, dairy=blue, histamine=orange).

const FLAG_STYLES: Record<string, { label: string; className: string }> = {
  'high-histamine': { label: 'Histamine', className: 'bg-orange-100 text-orange-800' },
  'high-fodmap': { label: 'FODMAP', className: 'bg-purple-100 text-purple-800' },
  gluten: { label: 'Gluten', className: 'bg-red-100 text-red-800' },
  dairy: { label: 'Dairy', className: 'bg-blue-100 text-blue-800' },
}

export function DietFlagPills({ flags }: { flags: string[] }) {
  if (!flags || flags.length === 0) return null
  return (
    <span className="inline-flex flex-wrap gap-0.5">
      {flags.map((flag) => {
        const style = FLAG_STYLES[flag] ?? { label: flag, className: 'bg-gray-100 text-gray-600' }
        return (
          <span
            key={flag}
            className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-none ${style.className}`}
          >
            {style.label}
          </span>
        )
      })}
    </span>
  )
}
