'use client'

import { Pill } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { SupplementPicker } from '@/components/checkin/supplement-picker'

interface SupplementsCardProps {
  value: string
  onChange: (v: string) => void
  onTouched: () => void
}

export function SupplementsCard({ value, onChange, onTouched }: SupplementsCardProps) {
  return (
    <Card className="col-span-12 lg:col-span-4">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
          <Pill className="size-4" />
          Supplements
        </CardTitle>
      </CardHeader>
      <CardContent>
        <SupplementPicker
          value={value}
          onChange={(v) => {
            onTouched()
            onChange(v)
          }}
        />
      </CardContent>
    </Card>
  )
}
