'use client'

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { NotesInput } from '@/components/checkin/notes-input'

interface NotesCardProps {
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
}: NotesCardProps) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
          Notes
        </CardTitle>
      </CardHeader>
      <CardContent>
        <NotesInput
          value={value}
          onChange={onChange}
          onEditStart={onEditStart}
          onBlur={onBlur}
          registerDraftFlush={registerDraftFlush}
        />
      </CardContent>
    </Card>
  )
}
