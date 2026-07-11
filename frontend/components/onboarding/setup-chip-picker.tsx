'use client'

import { cn } from '@/lib/utils'

interface SetupChipPickerProps {
  items: Array<{ id: string; label: string }>
  selected: string[]
  onChange: (next: string[]) => void
  isLoading?: boolean
}

export function SetupChipPicker({
  items,
  selected,
  onChange,
  isLoading = false,
}: SetupChipPickerProps) {
  const selectedSet = new Set(selected)

  function toggle(id: string) {
    if (selectedSet.has(id)) {
      onChange(selected.filter((value) => value !== id))
      return
    }
    onChange([...selected, id])
  }

  if (isLoading) {
    return (
      <div className="flex min-h-[120px] items-center justify-center text-sm text-muted-foreground">
        Loading suggestions…
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No suggestions available right now. You can add items later in Customize.
      </p>
    )
  }

  return (
    <div className="grid max-h-56 grid-cols-2 gap-2 overflow-y-auto pr-1 sm:grid-cols-3">
      {items.map((item) => {
        const isSelected = selectedSet.has(item.id)
        return (
          <button
            key={item.id}
            type="button"
            aria-pressed={isSelected}
            onClick={() => toggle(item.id)}
            className={cn(
              'min-h-[48px] rounded-xl border px-2 py-2 text-left text-sm font-medium transition-colors',
              isSelected
                ? 'border-primary bg-primary text-primary-foreground'
                : 'border-border bg-background text-muted-foreground hover:bg-muted/50',
            )}
          >
            {item.label}
          </button>
        )
      })}
    </div>
  )
}
