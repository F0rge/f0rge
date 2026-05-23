'use client'

import { useState } from 'react'
import { BarChart2, Plus } from 'lucide-react'
import { toast } from 'sonner'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  useTrackers,
  useCreateTracker,
  useUpdateTracker,
  useEntryTrackerValues,
  useUpsertTrackerValue,
} from '@/lib/api/hooks'
import { ApiError } from '@/lib/api/client'
import type { TrackerKind } from '@/lib/api/types'
import { TrackerRow } from './components/TrackerRow'

// Maps seeded tracker names to the corresponding CheckinBoard prop handlers.
// Keeps the dual-source wiring explicit and avoids scattered if/else chains.
const SEEDED_NAMES = new Set(['Alcohol units', 'Caffeine servings', 'Sick', 'Hot shower'])

interface TrackersCardProps {
  // Seeded tracker values — wired to CheckinBoard state (existing autosave path)
  alcoholUnits: number
  onAlcoholUnitsChange: (v: number) => void
  caffeineServings: number
  onCaffeineServingsChange: (v: number) => void
  sick: boolean
  onSickChange: (v: boolean) => void
  hotShower: boolean
  onHotShowerChange: (v: boolean) => void
  // Date so the card can fetch custom tracker values
  date: string
}

// ── Add tracker form ───────────────────────────────────────────────────────────
// Defined at module scope to avoid react-hooks/static-components violation.

interface AddTrackerFormProps {
  onClose: () => void
}

function AddTrackerForm({ onClose }: AddTrackerFormProps) {
  const [name, setName] = useState('')
  const [kind, setKind] = useState<TrackerKind>('counter')
  const [icon, setIcon] = useState('')
  const [unit, setUnit] = useState('')

  const createTracker = useCreateTracker()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) return

    try {
      await createTracker.mutateAsync({
        name: name.trim(),
        kind,
        icon: icon.trim() || null,
        unit: kind === 'counter' && unit.trim() ? unit.trim() : null,
      })
      onClose()
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        toast.error('A tracker with this name already exists')
      } else {
        console.error(err)
        toast.error('Failed to create tracker. Please try again.')
      }
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 rounded-xl border border-border bg-muted/40 p-3">
      <div className="space-y-1.5">
        <Label htmlFor="tracker-name" className="text-xs">Name</Label>
        <Input
          id="tracker-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Glasses of water"
          autoFocus
          required
        />
      </div>

      <div className="space-y-1.5">
        <Label className="text-xs">Type</Label>
        <div className="flex gap-2">
          {(['counter', 'binary'] as TrackerKind[]).map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setKind(k)}
              className={`flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-all ${
                kind === k
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'border-border bg-background text-foreground hover:bg-muted'
              }`}
            >
              {k === 'counter' ? 'Counter' : 'Toggle'}
            </button>
          ))}
        </div>
      </div>

      <div className="flex gap-2">
        <div className="flex-1 space-y-1.5">
          <Label htmlFor="tracker-icon" className="text-xs">Icon (optional)</Label>
          <Input
            id="tracker-icon"
            value={icon}
            onChange={(e) => setIcon(e.target.value)}
            placeholder="emoji or icon name"
          />
        </div>
        {kind === 'counter' && (
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="tracker-unit" className="text-xs">Unit (optional)</Label>
            <Input
              id="tracker-unit"
              value={unit}
              onChange={(e) => setUnit(e.target.value)}
              placeholder="e.g. glass"
            />
          </div>
        )}
      </div>

      <div className="flex gap-2">
        <Button
          type="submit"
          size="sm"
          disabled={!name.trim() || createTracker.isPending}
          className="flex-1"
        >
          {createTracker.isPending ? 'Adding…' : 'Add tracker'}
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={onClose}>
          Cancel
        </Button>
      </div>
    </form>
  )
}

// ── Main card ──────────────────────────────────────────────────────────────────

export function TrackersCard({
  alcoholUnits, onAlcoholUnitsChange,
  caffeineServings, onCaffeineServingsChange,
  sick, onSickChange,
  hotShower, onHotShowerChange,
  date,
}: TrackersCardProps) {
  const [showAddForm, setShowAddForm] = useState(false)

  const { data: trackers = [] } = useTrackers()
  const { data: trackerValues = [] } = useEntryTrackerValues(date)
  const upsertValue = useUpsertTrackerValue(date)
  const updateTracker = useUpdateTracker()

  // Only render non-archived trackers, sorted by position
  const visibleTrackers = trackers
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

  function handleArchive(trackerId: number, name: string) {
    updateTracker.mutate(
      { id: trackerId, data: { archived: true } },
      {
        onError: () => toast.error(`Failed to archive "${name}"`),
      },
    )
  }

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
          <BarChart2 className="size-4" />
          Daily trackers
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {visibleTrackers.length === 0 && !showAddForm && (
          <p className="text-sm text-muted-foreground">No trackers yet.</p>
        )}

        {visibleTrackers.map((tracker) => {
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
              onArchive={
                !tracker.is_seed
                  ? () => handleArchive(tracker.id, tracker.name)
                  : undefined
              }
            />
          )
        })}

        {showAddForm ? (
          <AddTrackerForm onClose={() => setShowAddForm(false)} />
        ) : (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="w-full gap-1.5"
            onClick={() => setShowAddForm(true)}
          >
            <Plus className="size-3.5" />
            Add tracker
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
