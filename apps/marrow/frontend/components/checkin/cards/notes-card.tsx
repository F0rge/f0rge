'use client'

import { Card, CardContent } from '@f0rge/ui'
import { NotesInput } from '@/components/checkin/notes-input'
import { CheckinCardHeader } from '@/components/checkin/checkin-card-header'
import type { CheckinCardCollapseProps } from '@/components/checkin/checkin-card-collapse'

interface NotesCardProps extends CheckinCardCollapseProps {
  entryKey: string
  value: string
  onChange: (v: string) => void
  onEditStart: () => void
  onBlur: (flushedNotes: string) => void
  registerDraftFlush: (flush: () => string) => void
}

export function NotesCard({
  entryKey,
  value,
  onChange,
  onEditStart,
  onBlur,
  registerDraftFlush,
  collapsed,
  onToggleCollapsed,
}: NotesCardProps) {
  return (
    <Card className="h-full">
      <CheckinCardHeader
        title="Notes"
        collapsed={collapsed}
        onToggleCollapsed={onToggleCollapsed}
      />
      {!collapsed && (
        <CardContent>
          <NotesInput
            key={entryKey}
            value={value}
            onChange={onChange}
            onEditStart={onEditStart}
            onBlur={onBlur}
            registerDraftFlush={registerDraftFlush}
          />
        </CardContent>
      )}
    </Card>
  )
}
