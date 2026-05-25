'use client'

import { useState } from 'react'
import { Search } from 'lucide-react'
import { cn } from '@/lib/utils'

interface CatalogItem {
  key: string
  label: string
  archived: boolean
}

interface CatalogSectionProps {
  title: string
  items: CatalogItem[]
  onToggleArchive: (key: string, archived: boolean) => void
  selectedCount: number
  totalCount: number
}

export function CatalogSection({
  title,
  items,
  onToggleArchive,
  selectedCount,
  totalCount,
}: CatalogSectionProps) {
  const [search, setSearch] = useState('')

  const filtered = search.trim()
    ? items.filter(
        (item) =>
          item.label.toLowerCase().includes(search.toLowerCase()) ||
          item.key.toLowerCase().includes(search.toLowerCase()),
      )
    : items

  return (
    <div className="mb-6">
      {/* Section heading */}
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold">{title}</h2>
        <span className="text-xs text-muted-foreground">
          {selectedCount} of {totalCount} active
        </span>
      </div>

      {/* Search */}
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

      {/* Item list */}
      <div className="overflow-hidden rounded-md border">
        {filtered.length === 0 ? (
          <p className="px-3 py-4 text-center text-xs text-muted-foreground">
            No items match your search.
          </p>
        ) : (
          filtered.map((item) => {
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
          })
        )}
      </div>

      {/* Request stub */}
      <button
        type="button"
        disabled
        className="mt-2 w-full rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground opacity-50 cursor-not-allowed"
      >
        + Request a new item
      </button>
    </div>
  )
}
