'use client'

import { useMemo, useRef, useState } from 'react'
import { Search } from 'lucide-react'
import { Input } from '@f0rge/ui'
import { cn } from '@f0rge/ui'
import { useClampedHeightBelow, useFocusScrollIntoView } from '@/hooks/keyboard-viewport'
import { useKeyboardOpen } from '@/hooks/use-keyboard-open'

interface PickerItem {
  id: string
  label: string
}

interface SetupSearchPickerProps {
  curatedItems: PickerItem[]
  searchableItems: PickerItem[]
  selected: string[]
  onChange: (next: string[]) => void
  isLoading?: boolean
  searchPlaceholder?: string
  addLaterHint: string
}

function matchesQuery(item: PickerItem, query: string): boolean {
  const normalized = query.toLowerCase()
  return (
    item.label.toLowerCase().includes(normalized) ||
    item.id.toLowerCase().includes(normalized)
  )
}

export function SetupSearchPicker({
  curatedItems,
  searchableItems,
  selected,
  onChange,
  isLoading = false,
  searchPlaceholder = 'Search…',
  addLaterHint,
}: SetupSearchPickerProps) {
  const [search, setSearch] = useState('')
  const trimmedSearch = search.trim()
  const searchAnchorRef = useRef<HTMLDivElement>(null)
  const onFocusScroll = useFocusScrollIntoView()
  const keyboardOpen = useKeyboardOpen()
  const gridMaxHeight = useClampedHeightBelow(searchAnchorRef, {
    enabled: keyboardOpen && trimmedSearch.length > 0,
  })
  const selectedSet = useMemo(() => new Set(selected), [selected])

  const visibleItems = useMemo(() => {
    if (!trimmedSearch) {
      const curatedIds = new Set(curatedItems.map((item) => item.id))
      const selectedExtras = searchableItems.filter(
        (item) => selectedSet.has(item.id) && !curatedIds.has(item.id),
      )
      return [...curatedItems, ...selectedExtras]
    }
    const matching = searchableItems.filter((item) =>
      matchesQuery(item, trimmedSearch),
    )
    const visibleIds = new Set(matching.map((item) => item.id))
    const selectedNotVisible = [...curatedItems, ...searchableItems].filter(
      (item) => selectedSet.has(item.id) && !visibleIds.has(item.id),
    )
    const dedupedIds = new Set(visibleIds)
    const selectedExtras = selectedNotVisible.filter((item) => {
      if (dedupedIds.has(item.id)) return false
      dedupedIds.add(item.id)
      return true
    })
    return [...matching, ...selectedExtras]
  }, [curatedItems, searchableItems, trimmedSearch, selectedSet])

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

  if (curatedItems.length === 0 && searchableItems.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No suggestions available right now. {addLaterHint}
      </p>
    )
  }

  return (
    <div className="space-y-3">
      <div ref={searchAnchorRef} className="relative">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="search"
          value={search}
          onFocus={onFocusScroll}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={searchPlaceholder}
          className="h-9 pl-8"
        />
      </div>

      {trimmedSearch && visibleItems.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No matches. {addLaterHint}
        </p>
      ) : (
        <div
          className="grid max-h-56 grid-cols-2 gap-2 overflow-y-auto pr-1 sm:grid-cols-3"
          style={gridMaxHeight != null ? { maxHeight: gridMaxHeight } : undefined}
        >
          {visibleItems.map((item) => {
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
      )}

      {!trimmedSearch && (
        <p className="text-xs text-muted-foreground">
          Search to find more options. {addLaterHint}
        </p>
      )}
    </div>
  )
}
