'use client'

import { Card, CardContent } from '@/components/ui/card'
import { NotesInput } from '@/components/checkin/notes-input'
import { CheckinCardHeader } from '@/components/checkin/checkin-card-header'
import type { CheckinCardCollapseProps } from '@/components/checkin/checkin-card-collapse'

interface NotesCardProps extends CheckinCardCollapseProps {
  value: string
  onChange: (v: string) => void
  onEditStart: () => void
  onBlur: (flushedNotes: string) => void
  registerDraftFlush: (flush: () => string) => void
}

export function NotesCard({
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
