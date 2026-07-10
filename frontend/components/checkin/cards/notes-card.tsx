'use client'

import { Card, CardContent } from '@/components/ui/card'
import { NotesInput } from '@/components/checkin/notes-input'
import { CheckinCardHeader } from '@/components/checkin/checkin-card-header'
import type { CheckinCardCollapseProps } from '@/components/checkin/checkin-card-collapse'

interface NotesCardProps extends CheckinCardCollapseProps {
  value: string
  onChange: (v: string) => void
  onBlur: () => void
}

export function NotesCard({ value, onChange, onBlur, collapsed, onToggleCollapsed }: NotesCardProps) {
  return (
    <Card className="h-full">
      <CheckinCardHeader
        title="Notes"
        collapsed={collapsed}
        onToggleCollapsed={onToggleCollapsed}
      />
      {!collapsed && (
        <CardContent>
          <NotesInput value={value} onChange={onChange} onBlur={onBlur} />
        </CardContent>
      )}
    </Card>
  )
}
