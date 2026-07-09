'use client'

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { SupplementPicker } from '@/components/checkin/supplement-picker'
import { TierPill } from '@/components/customize/tier-pill'

interface SupplementsCardProps {
  value: string
  onChange: (v: string) => void
  onTouched: () => void
}

export function SupplementsCard({ value, onChange, onTouched }: SupplementsCardProps) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
          Supplements
          <TierPill tier="catalog" />
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
