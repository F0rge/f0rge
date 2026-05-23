'use client'

import { Activity } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { ScaleInput } from '@/components/checkin/scale-input'
import { BristolInput } from '@/components/checkin/bristol-input'
import type { StoolStatus } from '@/lib/api/types'

interface GutCardProps {
  bloating: number
  onBloatingChange: (v: number) => void
  stoolStatus: StoolStatus
  onStoolStatusChange: (v: StoolStatus) => void
  bristolType: number | null
  onBristolTypeChange: (v: number | null) => void
  jointPain: number
  onJointPainChange: (v: number) => void
}

export function GutCard({
  bloating, onBloatingChange,
  stoolStatus, onStoolStatusChange,
  bristolType, onBristolTypeChange,
  jointPain, onJointPainChange,
}: GutCardProps) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
          <Activity className="size-4" />
          Gut
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <ScaleInput
          label="Bloating"
          value={bloating}
          onChange={(v) => onBloatingChange(v as number)}
          options={[
            { value: 0, label: 'None' },
            { value: 1, label: 'Mild' },
            { value: 2, label: 'Moderate' },
            { value: 3, label: 'Severe' },
          ]}
        />
        <div className="space-y-3">
          <ScaleInput
            label="Stool"
            value={stoolStatus}
            onChange={(v) => onStoolStatusChange(v as StoolStatus)}
            options={[
              { value: 'normal', label: 'Normal' },
              { value: 'abnormal', label: 'Abnormal' },
              { value: 'none', label: 'No movement' },
            ]}
          />
          {stoolStatus === 'abnormal' && (
            <BristolInput value={bristolType} onChange={onBristolTypeChange} />
          )}
        </div>
        <ScaleInput
          label="Joint pain / crepitus"
          value={jointPain}
          onChange={(v) => onJointPainChange(v as number)}
          options={[
            { value: 0, label: 'None' },
            { value: 1, label: 'Mild' },
            { value: 2, label: 'Moderate' },
            { value: 3, label: 'Severe' },
          ]}
        />
      </CardContent>
    </Card>
  )
}
