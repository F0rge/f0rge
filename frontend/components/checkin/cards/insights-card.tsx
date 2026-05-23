'use client'

import { Sparkles } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { MiniBars } from './components/MiniBars'
import { PatternBox } from './components/PatternBox'
import type { Entry } from '@/lib/api/types'
import type { Pattern } from '@/lib/checkin/patterns'

function histamineLoad(entry: Entry): number {
  const val = entry.photo_signal?.scores?.histamine_load
  if (typeof val !== 'number' || isNaN(val)) return 0
  return val
}

function sleepColorClass(val: number | null): string {
  if (val === 3) return 'bg-emerald-500'
  if (val === 2) return 'bg-amber-500'
  return 'bg-red-500'
}

function bloatingColorClass(val: number | null): string {
  if (val === 0) return 'bg-emerald-500'
  if (val === 3) return 'bg-red-500'
  return 'bg-amber-500'
}

// Build a per-bar color array for sleep/bloating (today bar picks color dynamically).
// For MiniBars we only pass today's dynamic class; the component handles historicals.
// However sleep/bloating today may differ from previous days — we use a single colorClass
// for "today" bar which MiniBars applies only to the last bar.

interface InsightsCardProps {
  today: Entry | null
  last7: Entry[]  // most-recent-first, NOT including today
  pattern: Pattern | null
}

export function InsightsCard({ today, last7, pattern }: InsightsCardProps) {
  // Build ascending arrays (oldest → today). Most-recent-first last7 reversed + today.
  const ascendingPast = [...last7].reverse()
  const allDays = today ? [...ascendingPast, today] : ascendingPast
  const window7 = allDays.slice(-7)  // up to 7 most recent (today last)

  const histamineValues = window7.map((e) => histamineLoad(e))
  const sleepValues = window7.map((e) => e.sleep_quality)
  const bloatingValues = window7.map((e) => e.bloating)

  const todayHistamine = today ? histamineLoad(today) : null
  const todaySleep = today?.sleep_quality ?? null
  const todayBloating = today?.bloating ?? null

  const histamineTodayClass = 'bg-orange-500'
  const sleepTodayClass = sleepColorClass(todaySleep)
  const bloatingTodayClass = bloatingColorClass(todayBloating)

  return (
    <Card className="col-span-12 lg:col-span-4">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
          <Sparkles className="size-4 text-indigo-500" />
          Today vs last 7 days
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Histamine row */}
        <div className="flex items-center gap-2">
          <span className="text-xs w-20 text-muted-foreground shrink-0">Histamine</span>
          <MiniBars
            values={histamineValues}
            colorClass={histamineTodayClass}
            maxOverride={6}
          />
          <span className="text-xs font-semibold text-orange-700 dark:text-orange-400 w-6 text-right">
            {todayHistamine ?? '—'}
          </span>
        </div>

        {/* Sleep row */}
        <div className="flex items-center gap-2">
          <span className="text-xs w-20 text-muted-foreground shrink-0">Sleep</span>
          <MiniBars
            values={sleepValues}
            colorClass={sleepTodayClass}
            maxOverride={3}
          />
          <span className={[
            'text-xs font-semibold w-12 text-right',
            todaySleep === 3 ? 'text-emerald-700 dark:text-emerald-400' :
            todaySleep === 1 ? 'text-red-600 dark:text-red-400' :
            'text-amber-700 dark:text-amber-400',
          ].join(' ')}>
            {todaySleep === 3 ? 'Good' : todaySleep === 2 ? 'OK' : todaySleep === 1 ? 'Poor' : '—'}
          </span>
        </div>

        {/* Bloating row */}
        <div className="flex items-center gap-2">
          <span className="text-xs w-20 text-muted-foreground shrink-0">Bloating</span>
          <MiniBars
            values={bloatingValues}
            colorClass={bloatingTodayClass}
            maxOverride={3}
          />
          <span className={[
            'text-xs font-semibold w-10 text-right',
            todayBloating === 0 ? 'text-emerald-700 dark:text-emerald-400' :
            todayBloating === 3 ? 'text-red-600 dark:text-red-400' :
            'text-amber-700 dark:text-amber-400',
          ].join(' ')}>
            {todayBloating === 0 ? 'None' : todayBloating === 1 ? 'Mild' : todayBloating === 2 ? 'Mod.' : todayBloating === 3 ? 'Sev.' : '—'}
          </span>
        </div>

        {pattern && <PatternBox pattern={pattern} />}
      </CardContent>
    </Card>
  )
}
