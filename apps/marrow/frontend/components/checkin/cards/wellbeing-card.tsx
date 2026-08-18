'use client'

import { Card, CardContent } from '@f0rge/ui'
import { ScaleInput } from '@/components/checkin/scale-input'
import { CheckinCardHeader } from '@/components/checkin/checkin-card-header'
import type { CheckinCardCollapseProps } from '@/components/checkin/checkin-card-collapse'

interface WellbeingCardProps extends CheckinCardCollapseProps {
  overall: number | null
  onOverallChange: (v: number) => void
  sleepQuality: number | null
  onSleepQualityChange: (v: number) => void
  stress: number | null
  onStressChange: (v: number) => void
  // v4 entries (and any new, not-yet-created day) use 5-point core scales.
  // Legacy entries (schema_version <= 3) keep their original 3-point scales
  // so old stored values keep meaning what they meant when they were saved.
  fivePoint: boolean
}

export function WellbeingCard({
  overall, onOverallChange,
  sleepQuality, onSleepQualityChange,
  stress, onStressChange,
  fivePoint,
  collapsed,
  onToggleCollapsed,
}: WellbeingCardProps) {
  return (
    <Card className="h-full">
      <CheckinCardHeader
        title="Wellbeing"
        tier="core"
        collapsed={collapsed}
        onToggleCollapsed={onToggleCollapsed}
      />
      {!collapsed && (
      <CardContent className="space-y-5">
        <ScaleInput
          label="How was your day?"
          value={overall}
          onChange={(v) => onOverallChange(v as number)}
          options={
            fivePoint
              ? [
                  { value: 1, label: 'Awful' },
                  { value: 2, label: 'Poor' },
                  { value: 3, label: 'OK' },
                  { value: 4, label: 'Good' },
                  { value: 5, label: 'Great' },
                ]
              : [
                  { value: 1, label: 'Very Poor' },
                  { value: 2, label: 'Standard' },
                  { value: 3, label: 'Very Good' },
                ]
          }
        />
        <ScaleInput
          label="Sleep quality (last night)"
          value={sleepQuality}
          onChange={(v) => onSleepQualityChange(v as number)}
          options={
            fivePoint
              ? [
                  { value: 1, label: 'Awful' },
                  { value: 2, label: 'Poor' },
                  { value: 3, label: 'OK' },
                  { value: 4, label: 'Good' },
                  { value: 5, label: 'Great' },
                ]
              : [
                  { value: 1, label: 'Poor' },
                  { value: 2, label: 'OK' },
                  { value: 3, label: 'Good' },
                ]
          }
        />
        <ScaleInput
          label="Stress level"
          value={stress}
          onChange={(v) => onStressChange(v as number)}
          options={
            fivePoint
              ? [
                  { value: 1, label: 'None' },
                  { value: 2, label: 'Low' },
                  { value: 3, label: 'Med' },
                  { value: 4, label: 'High' },
                  { value: 5, label: 'Severe' },
                ]
              : [
                  { value: 1, label: 'Low' },
                  { value: 2, label: 'Medium' },
                  { value: 3, label: 'High' },
                ]
          }
        />
      </CardContent>
      )}
    </Card>
  )
}
