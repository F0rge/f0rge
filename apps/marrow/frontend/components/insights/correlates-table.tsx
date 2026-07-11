'use client'

import { useState } from 'react'
import { Loader2, ChevronUp, ChevronDown } from 'lucide-react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@f0rge/ui'
import { Badge } from '@f0rge/ui'
import { useInsightsCorrelates } from '@/lib/api/hooks'
import { cn } from '@f0rge/ui'
import type { CorrelateRow } from '@/lib/api/types'

interface Props {
  outcome: string
  start: string
  end: string
}

const CATEGORIES = [
  'all',
  'food',
  'supplement',
  'sleep',
  'weather',
  'treatment',
  'symptom',
  'metric',
] as const

type SortKey = 'rho' | 'n' | 'best_lag'
type SortDir = 'asc' | 'desc'

function sortIcon(col: SortKey, sortKey: SortKey, sortDir: SortDir) {
  if (sortKey !== col) return null
  return sortDir === 'desc' ? (
    <ChevronDown className="ml-0.5 inline size-3" />
  ) : (
    <ChevronUp className="ml-0.5 inline size-3" />
  )
}

function CorrelateRows({
  rows,
  label,
}: {
  rows: CorrelateRow[]
  label: string
}) {
  const [sortKey, setSortKey] = useState<SortKey>('rho')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'))
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  const sorted = [...rows].sort((a, b) => {
    const aVal = sortKey === 'rho' ? Math.abs(a.rho) : a[sortKey]
    const bVal = sortKey === 'rho' ? Math.abs(b.rho) : b[sortKey]
    return sortDir === 'desc' ? bVal - aVal : aVal - bVal
  })

  if (rows.length === 0) {
    return (
      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {label}
        </p>
        <p className="text-sm text-muted-foreground">No correlates found.</p>
      </div>
    )
  }

  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <div className="overflow-x-auto rounded-lg ring-1 ring-foreground/10">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="px-2 py-1.5 text-left font-medium">Feature</th>
              <th
                className="cursor-pointer px-2 py-1.5 text-right font-medium"
                onClick={() => handleSort('rho')}
              >
                ρ{sortIcon('rho', sortKey, sortDir)}
              </th>
              <th
                className="cursor-pointer px-2 py-1.5 text-right font-medium"
                onClick={() => handleSort('n')}
              >
                n{sortIcon('n', sortKey, sortDir)}
              </th>
              <th
                className="cursor-pointer px-2 py-1.5 text-right font-medium"
                onClick={() => handleSort('best_lag')}
              >
                lag{sortIcon('best_lag', sortKey, sortDir)}
              </th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr key={row.feature} className="border-b last:border-0">
                <td className="px-2 py-1.5">
                  <div className="flex flex-col gap-0.5">
                    <span className="font-medium leading-tight">{row.label}</span>
                    <Badge variant="secondary" className="w-fit text-[10px]">
                      {row.category}
                    </Badge>
                  </div>
                </td>
                <td
                  className={cn(
                    'px-2 py-1.5 text-right tabular-nums font-medium',
                    row.rho > 0
                      ? 'text-green-700 dark:text-green-400'
                      : 'text-red-700 dark:text-red-400',
                  )}
                >
                  {row.rho.toFixed(3)}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums text-muted-foreground">
                  {row.n}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums text-muted-foreground">
                  {row.best_lag}d
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function CorrelatesTable({ outcome, start, end }: Props) {
  const [activeCategory, setActiveCategory] = useState<string>('all')

  const { data, isLoading, isError } = useInsightsCorrelates(
    outcome,
    start,
    end,
    activeCategory,
  )

  return (
    <div className="space-y-4">
      <Tabs
        value={activeCategory}
        onValueChange={setActiveCategory}
      >
        <TabsList className="flex h-auto w-full flex-wrap gap-1 bg-transparent p-0">
          {CATEGORIES.map((cat) => (
            <TabsTrigger
              key={cat}
              value={cat}
              className="h-7 rounded-md px-2 text-xs capitalize"
            >
              {cat}
            </TabsTrigger>
          ))}
        </TabsList>

        {CATEGORIES.map((cat) => (
          <TabsContent key={cat} value={cat}>
            {/* content rendered below, outside tabs panel, to avoid double rendering */}
          </TabsContent>
        ))}
      </Tabs>

      {isLoading && (
        <div className="flex items-center justify-center py-6">
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
        </div>
      )}

      {isError && (
        <p className="text-sm text-destructive">Failed to load correlates.</p>
      )}

      {data && !isLoading && (
        <div className="space-y-6">
          <CorrelateRows rows={data.positive.slice(0, 15)} label="Top positive" />
          <CorrelateRows rows={data.negative.slice(0, 15)} label="Top negative" />
        </div>
      )}
    </div>
  )
}
