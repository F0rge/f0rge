'use client'

import { FileText } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { NotesInput } from '@/components/checkin/notes-input'

interface NotesCardProps {
  value: string
  onChange: (v: string) => void
  onBlur: () => void
}

export function NotesCard({ value, onChange, onBlur }: NotesCardProps) {
  return (
    <Card className="col-span-12 lg:col-span-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
          <FileText className="size-4" />
          Notes
        </CardTitle>
      </CardHeader>
      <CardContent>
        <NotesInput value={value} onChange={onChange} onBlur={onBlur} />
      </CardContent>
    </Card>
  )
}
