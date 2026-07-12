'use client'

import { Card, CardContent } from '@f0rge/ui'
import { ScaleInput } from '@/components/checkin/scale-input'
import { BristolInput } from '@/components/checkin/bristol-input'
import type { StoolStatus } from '@/lib/api/types'
import { CheckinCardHeader } from '@/components/checkin/checkin-card-header'
import type { CheckinCardCollapseProps } from '@/components/checkin/checkin-card-collapse'

interface GutCardProps extends CheckinCardCollapseProps {
  bloating: number
  onBloatingChange: (v: number) => void
  stoolStatus: StoolStatus
  onStoolStatusChange: (v: StoolStatus) => void
  bristolType: number | null
  onBristolTypeChange: (v: number | null) => void
  stoolCompleteness: 'complete' | 'incomplete' | null
  onStoolCompletenessChange: (v: 'complete' | 'incomplete') => void
}

export function GutCard({
  bloating, onBloatingChange,
  stoolStatus, onStoolStatusChange,
  bristolType, onBristolTypeChange,
  stoolCompleteness, onStoolCompletenessChange,
  collapsed,
  onToggleCollapsed,
}: GutCardProps) {
  return (
    <Card className="h-full">
      <CheckinCardHeader
        title="Gut"
        tier="core"
        collapsed={collapsed}
        onToggleCollapsed={onToggleCollapsed}
      />
      {!collapsed && (
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
              { value: 'none', label: 'Skipped' },
            ]}
          />
          {stoolStatus === 'abnormal' && (
            <BristolInput value={bristolType} onChange={onBristolTypeChange} />
          )}
          {stoolStatus !== 'none' && (
            <ScaleInput
              label="Completeness"
              value={stoolCompleteness ?? ''}
              onChange={(v) => onStoolCompletenessChange(v as 'complete' | 'incomplete')}
              options={[
                { value: 'complete', label: 'Complete' },
                { value: 'incomplete', label: 'Incomplete' },
              ]}
            />
          )}
        </div>
      </CardContent>
      )}
    </Card>
  )
}
