'use client'

import { useState } from 'react'
import { BarChart2, ChevronDown, Plus } from 'lucide-react'
import { toast } from 'sonner'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
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
import { IconPicker } from './components/IconPicker'

const SEEDED_NAMES = new Set(['Alcohol units', 'Caffeine servings', 'Sick', 'Hot shower'])

interface TrackersCardProps {
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

// ── Add tracker modal form ─────────────────────────────────────────────────────
// Defined at module scope to satisfy react-hooks/static-components rule.

interface AddTrackerModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  trackerCount: number
}

function AddTrackerModal({ open, onOpenChange, trackerCount }: AddTrackerModalProps) {
  const [name, setName] = useState('')
  const [kind, setKind] = useState<TrackerKind>('counter')
  const [icon, setIcon] = useState<string | null>(null)
  const [unit, setUnit] = useState('')

  const createTracker = useCreateTracker()

  function handleClose() {
    onOpenChange(false)
    // Reset form on close
    setName('')
    setKind('counter')
    setIcon(null)
    setUnit('')
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) return

    try {
      await createTracker.mutateAsync({
        name: name.trim(),
        kind,
        icon: icon ?? null,
        unit: kind === 'counter' && unit.trim() ? unit.trim() : null,
        position: trackerCount,
      })
      handleClose()
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
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>Add tracker</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Name */}
          <div className="space-y-1.5">
            <Label htmlFor="tracker-name" className="text-xs text-muted-foreground">
              Name
            </Label>
            <Input
              id="tracker-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Steps"
              autoFocus
              required
            />
          </div>

          {/* Type segmented control */}
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Type</Label>
            <div className="grid grid-cols-2 gap-1 p-1 bg-muted rounded-md">
              {(['counter', 'binary'] as TrackerKind[]).map((k) => (
                <button
                  key={k}
                  type="button"
                  onClick={() => setKind(k)}
                  className={`py-1.5 rounded text-xs font-medium transition-all ${
                    kind === k
                      ? 'bg-card shadow-sm text-foreground'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {k === 'counter' ? 'Counter' : 'Binary'}
                </button>
              ))}
            </div>
          </div>

          {/* Icon picker */}
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Icon</Label>
            <IconPicker value={icon} onChange={setIcon} />
          </div>

          {/* Unit — only for counter */}
          {kind === 'counter' && (
            <div className="space-y-1.5">
              <Label htmlFor="tracker-unit" className="text-xs text-muted-foreground">
                Unit (optional)
              </Label>
              <Input
                id="tracker-unit"
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                placeholder="e.g. glasses, mg, minutes"
              />
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="ghost" size="sm" onClick={handleClose}>
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={!name.trim() || createTracker.isPending}
            >
              {createTracker.isPending ? 'Adding…' : 'Add tracker'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
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
  const [showAddModal, setShowAddModal] = useState(false)
  const [showManage, setShowManage] = useState(false)

  const { data: allTrackers = [] } = useTrackers(true)
  const { data: trackerValues = [] } = useEntryTrackerValues(date)
  const upsertValue = useUpsertTrackerValue(date)
  const updateTracker = useUpdateTracker()

  const activeTrackers = allTrackers
    .filter((t) => !t.archived)
    .sort((a, b) => a.position - b.position || a.name.localeCompare(b.name))

  const archivedTrackers = allTrackers.filter((t) => t.archived)

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
      { onError: () => toast.error(`Failed to archive "${name}"`) },
    )
  }

  function handleRestore(trackerId: number, name: string) {
    updateTracker.mutate(
      { id: trackerId, data: { archived: false } },
      { onError: () => toast.error(`Failed to restore "${name}"`) },
    )
  }

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
            <BarChart2 className="size-4" />
            Daily trackers
          </span>
          <button
            type="button"
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
          >
            <Plus className="size-3.5" />
            Add
          </button>
        </CardTitle>
      </CardHeader>

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
                onArchive={
                  !tracker.is_seed ? () => handleArchive(tracker.id, tracker.name) : undefined
                }
              />
            )
          })}
        </ul>

        {/* Manage trackers disclosure — only shown when archived trackers exist */}
        {archivedTrackers.length > 0 && (
          <div className="border-t border-border">
            <button
              type="button"
              onClick={() => setShowManage((v) => !v)}
              className="w-full px-4 py-3 text-xs text-muted-foreground hover:bg-muted
                transition-colors flex items-center justify-between"
            >
              <span>Manage trackers</span>
              <ChevronDown
                className={`size-4 transition-transform ${showManage ? 'rotate-180' : ''}`}
              />
            </button>

            {showManage && (
              <div className="border-t border-border bg-muted/30">
                <div className="px-4 py-2">
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Archived
                  </div>
                </div>
                <ul className="divide-y divide-border">
                  {archivedTrackers.map((tracker) => (
                    <TrackerRow
                      key={tracker.id}
                      tracker={tracker}
                      value={0}
                      onChange={() => {}}
                      archived
                      onRestore={() => handleRestore(tracker.id, tracker.name)}
                    />
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </CardContent>

      <AddTrackerModal
        open={showAddModal}
        onOpenChange={setShowAddModal}
        trackerCount={activeTrackers.length}
      />
    </Card>
  )
}
