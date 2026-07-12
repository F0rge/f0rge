'use client'

import { Card, CardContent } from '@f0rge/ui'
import {
  useTrackers,
  useEntryTrackerValues,
  useUpsertTrackerValue,
} from '@/lib/api/hooks'
import { CheckinCardHeader } from '@/components/checkin/checkin-card-header'
import type { CheckinCardCollapseProps } from '@/components/checkin/checkin-card-collapse'
import { TrackerRow } from './components/TrackerRow'

const SEEDED_NAMES = new Set(['Alcohol units', 'Caffeine servings', 'Sick', 'Hot shower'])

interface TrackersCardProps extends CheckinCardCollapseProps {
  alcoholUnits: number
  onAlcoholUnitsChange: (v: number) => void
  caffeineServings: number
  onCaffeineServingsChange: (v: number) => void
  sick: boolean
  onSickChange: (v: boolean) => void
  hotShower: boolean
  onHotShowerChange: (v: boolean) => void
  date: string
}

// ── Main card ──────────────────────────────────────────────────────────────────

export function TrackersCard({
  alcoholUnits, onAlcoholUnitsChange,
  caffeineServings, onCaffeineServingsChange,
  sick, onSickChange,
  hotShower, onHotShowerChange,
  date,
  collapsed,
  onToggleCollapsed,
}: TrackersCardProps) {
  const { data: allTrackers = [] } = useTrackers(true)
  const { data: trackerValues = [] } = useEntryTrackerValues(date)
  const upsertValue = useUpsertTrackerValue(date)

  const activeTrackers = allTrackers
    .filter((t) => !t.archived)
    .sort((a, b) => a.position - b.position || a.name.localeCompare(b.name))

  function getSeededValue(name: string): number {
    switch (name) {
      case 'Alcohol units': return alcoholUnits
      case 'Caffeine servings': return caffeineServings
      case 'Sick': return sick ? 1 : 0
      case 'Hot shower': return hotShower ? 1 : 0
      default: return 0
    }
  }

  function getSeededOnChange(name: string): (v: number) => void {
    switch (name) {
      case 'Alcohol units': return onAlcoholUnitsChange
      case 'Caffeine servings': return onCaffeineServingsChange
      case 'Sick': return (v) => onSickChange(v === 1)
      case 'Hot shower': return (v) => onHotShowerChange(v === 1)
      default: return () => {}
    }
  }

  function getCustomValue(trackerId: number): number {
    return trackerValues.find((tv) => tv.tracker_id === trackerId)?.value ?? 0
  }

  return (
    <Card className="h-full">
      <CheckinCardHeader
        title="Daily trackers"
        tier="custom"
        collapsed={collapsed}
        onToggleCollapsed={onToggleCollapsed}
      />

      {!collapsed && (
      <CardContent className="p-0">
        {activeTrackers.length === 0 && (
          <p className="px-4 pb-4 text-sm text-muted-foreground">No trackers yet.</p>
        )}

        <ul className="divide-y divide-border">
          {activeTrackers.map((tracker) => {
            const isSeeded = SEEDED_NAMES.has(tracker.name) && tracker.is_seed
            const value = isSeeded
              ? getSeededValue(tracker.name)
              : getCustomValue(tracker.id)
            const onChange = isSeeded
              ? getSeededOnChange(tracker.name)
              : (v: number) => upsertValue.mutate({ trackerId: tracker.id, value: v })

            return (
              <TrackerRow
                key={tracker.id}
                tracker={tracker}
                value={value}
                onChange={onChange}
              />
            )
          })}
        </ul>
      </CardContent>
      )}
    </Card>
  )
}
