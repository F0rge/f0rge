'use client'

import { Activity } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { ScaleInput } from '@/components/checkin/scale-input'
import { BristolInput } from '@/components/checkin/bristol-input'
import { cn } from '@/lib/utils'
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
  bristolBlocked: boolean
}

export function GutCard({
  bloating, onBloatingChange,
  stoolStatus, onStoolStatusChange,
  bristolType, onBristolTypeChange,
  jointPain, onJointPainChange,
  bristolBlocked,
}: GutCardProps) {
  return (
    <Card className={cn(
      'h-full transition-shadow',
      bristolBlocked && 'ring-2 ring-amber-400 ring-offset-2 ring-offset-background bg-amber-50/40 dark:bg-amber-950/20',
    )}>
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
            <>
              <BristolInput value={bristolType} onChange={onBristolTypeChange} />
              {bristolBlocked && (
                <p className="text-xs text-amber-600 dark:text-amber-400">
                  Pick a Bristol type to keep saving
                </p>
              )}
            </>
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
