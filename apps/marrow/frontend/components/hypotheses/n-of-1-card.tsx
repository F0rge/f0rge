'use client'

import { useState } from 'react'
import { Button, Input } from '@f0rge/ui'
import { handleMutationError } from '@f0rge/ui/api'
import { TextInput } from '@f0rge/ui/forms'
import { useNOf1, useUpdateNOf1 } from '@/lib/api/hooks'
import type { NOf1Slot } from '@/lib/api/types'

function SlotSummary({ slot }: { slot: NOf1Slot }) {
  return (
    <dl className="space-y-1.5 text-sm">
      <div>
        <dt className="text-xs font-semibold text-muted-foreground">Change</dt>
        <dd>{slot.change}</dd>
      </div>
      <div>
        <dt className="text-xs font-semibold text-muted-foreground">Start</dt>
        <dd>{slot.start}</dd>
      </div>
      <div>
        <dt className="text-xs font-semibold text-muted-foreground">Watch</dt>
        <dd>{slot.watch_field}</dd>
      </div>
      <div>
        <dt className="text-xs font-semibold text-muted-foreground">Stop rule</dt>
        <dd>{slot.stop_rule}</dd>
      </div>
    </dl>
  )
}

export function NOf1Card() {
  const { data: slot } = useNOf1()
  const update = useUpdateNOf1()
  const [editing, setEditing] = useState(false)
  const [change, setChange] = useState('')
  const [start, setStart] = useState('')
  const [watchField, setWatchField] = useState('')
  const [stopRule, setStopRule] = useState('')

  function toggleEdit() {
    if (!editing) {
      setChange(slot?.change ?? '')
      setStart(slot?.start ?? '')
      setWatchField(slot?.watch_field ?? '')
      setStopRule(slot?.stop_rule ?? '')
    }
    setEditing((open) => !open)
  }

  async function onSave() {
    try {
      await update.mutateAsync({
        change,
        start,
        watch_field: watchField,
        stop_rule: stopRule,
      })
      setEditing(false)
    } catch (err) {
      handleMutationError(err, 'Could not save the n-of-1 slot.')
    }
  }

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Active n-of-1 slot</h2>
        <Button type="button" variant="outline" size="sm" onClick={toggleEdit}>
          {editing ? 'Cancel' : slot ? 'Edit' : 'Set'}
        </Button>
      </div>
      {!editing && slot && <SlotSummary slot={slot} />}
      {!editing && !slot && (
        <p className="text-sm text-muted-foreground">No experiment slot yet. One active change at a time.</p>
      )}
      {editing && (
        <form
          className="space-y-2"
          onSubmit={(event) => {
            event.preventDefault()
            void onSave()
          }}
        >
          <Input required value={change} onChange={(e) => setChange(e.target.value)} placeholder="Change" />
          <TextInput
            required
            label="Start"
            type="date"
            value={start}
            onChange={(e) => setStart(e.currentTarget.value)}
          />
          <Input
            required
            value={watchField}
            onChange={(e) => setWatchField(e.target.value)}
            placeholder="Watch field"
          />
          <Input required value={stopRule} onChange={(e) => setStopRule(e.target.value)} placeholder="Stop rule" />
          <Button type="submit" size="sm" disabled={update.isPending}>
            Save slot
          </Button>
        </form>
      )}
    </section>
  )
}
