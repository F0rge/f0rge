'use client'

import { useState } from 'react'
import { Plus, Search } from 'lucide-react'
import { cn } from '@f0rge/ui'

interface CatalogItem {
  key: string
  label: string
  archived: boolean
}

interface SuggestionItem {
  key: string
  label: string
}

interface CatalogSectionProps {
  title: string
  items: CatalogItem[]
  suggestions?: SuggestionItem[]
  onToggleArchive: (key: string, archived: boolean) => void
  onAddSuggestion?: (key: string, label: string) => void
  selectedCount: number
  totalCount: number
}

export function CatalogSection({
  title,
  items,
  suggestions = [],
  onToggleArchive,
  onAddSuggestion,
  selectedCount,
  totalCount,
}: CatalogSectionProps) {
  const [search, setSearch] = useState('')
  const existingKeys = new Set(items.map((item) => item.key))
  const availableSuggestions = suggestions.filter((item) => !existingKeys.has(item.key))

  const filteredItems = search.trim()
    ? items.filter(
        (item) =>
          item.label.toLowerCase().includes(search.toLowerCase()) ||
          item.key.toLowerCase().includes(search.toLowerCase()),
      )
    : items

  const filteredSuggestions = search.trim()
    ? availableSuggestions.filter(
        (item) =>
          item.label.toLowerCase().includes(search.toLowerCase()) ||
          item.key.toLowerCase().includes(search.toLowerCase()),
      )
    : []

  const showSuggestions = search.trim().length > 0 && filteredSuggestions.length > 0

  return (
    <div className="mb-6">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold">{title}</h2>
        <span className="text-xs text-muted-foreground">
          {selectedCount} of {totalCount} active
        </span>
      </div>

      <div className="relative mb-2">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={`Search ${title.toLowerCase()}…`}
          className={cn(
            'h-8 w-full rounded-md border bg-background pl-8 pr-3 text-sm',
            'placeholder:text-muted-foreground',
            'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1',
          )}
        />
      </div>

      <div className="overflow-hidden rounded-md border">
        {filteredItems.length === 0 && !showSuggestions ? (
          <p className="px-3 py-4 text-center text-xs text-muted-foreground">
            {search.trim()
              ? 'No items match your search.'
              : 'No items in your catalog yet. Search to add from suggestions.'}
          </p>
        ) : (
          <>
            {filteredItems.map((item) => {
              const isActive = !item.archived
              return (
                <label
                  key={item.key}
                  className={cn(
                    'flex cursor-pointer items-center gap-3 border-t px-3 py-2.5',
                    'first:border-t-0 hover:bg-muted/40 transition-colors',
                  )}
                >
                  <input
                    type="checkbox"
                    checked={isActive}
                    onChange={() => onToggleArchive(item.key, item.archived)}
                    className="size-4 shrink-0 accent-primary"
                  />
                  <span
                    className={cn(
                      'text-sm',
                      !isActive && 'text-muted-foreground line-through',
                    )}
                  >
                    {item.label}
                  </span>
                </label>
              )
            })}
            {showSuggestions &&
              filteredSuggestions.map((item) => (
                <div
                  key={`suggestion-${item.key}`}
                  className="flex items-center justify-between gap-3 border-t px-3 py-2.5"
                >
                  <span className="text-sm text-muted-foreground">{item.label}</span>
                  <button
                    type="button"
                    onClick={() => onAddSuggestion?.(item.key, item.label)}
                    className="inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-medium hover:bg-muted/50"
                  >
                    <Plus className="size-3" />
                    Add
                  </button>
                </div>
              ))}
          </>
        )}
      </div>
    </div>
  )
}
