'use client'

import { AlertCircle } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { SymptomPicker } from '@/components/checkin/symptom-picker'

interface SymptomsCardProps {
  value: Record<string, number>
  onChange: (v: Record<string, number>) => void
}

export function SymptomsCard({ value, onChange }: SymptomsCardProps) {
  return (
    <Card className="col-span-12 lg:col-span-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
          <AlertCircle className="size-4" />
          Symptoms today
        </CardTitle>
      </CardHeader>
      <CardContent>
        <SymptomPicker value={value} onChange={onChange} />
      </CardContent>
    </Card>
  )
}
