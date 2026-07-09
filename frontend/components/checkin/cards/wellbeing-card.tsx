'use client'

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { ScaleInput } from '@/components/checkin/scale-input'
import { TierPill } from '@/components/customize/tier-pill'

interface WellbeingCardProps {
  overall: number
  onOverallChange: (v: number) => void
  sleepQuality: number
  onSleepQualityChange: (v: number) => void
  stress: number
  onStressChange: (v: number) => void
  neuro: number
  onNeuroChange: (v: number) => void
  // v4 entries (and any new, not-yet-created day) use 5-point core scales.
  // Legacy entries (schema_version <= 3) keep their original 3-point scales
  // so old stored values keep meaning what they meant when they were saved.
  fivePoint: boolean
}

export function WellbeingCard({
  overall, onOverallChange,
  sleepQuality, onSleepQualityChange,
  stress, onStressChange,
  neuro, onNeuroChange,
  fivePoint,
}: WellbeingCardProps) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
          Wellbeing
          <TierPill tier="core" />
        </CardTitle>
      </CardHeader>
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
        <ScaleInput
          label="Neuro symptoms"
          value={neuro}
          onChange={(v) => onNeuroChange(v as number)}
          options={
            fivePoint
              ? [
                  // Single short words only — "Much worse"/"Much better" (two-word,
                  // 10-11 char) overflowed a 5-column segment at 390px and visually
                  // ran into the next label, even though each is under
                  // MAX_SCALE_LABEL_LENGTH. Every other 5-point row here uses
                  // single words for the same reason.
                  { value: 1, label: 'Worst' },
                  { value: 2, label: 'Worse' },
                  { value: 3, label: 'Base' },
                  { value: 4, label: 'Better' },
                  { value: 5, label: 'Best' },
                ]
              : [
                  { value: -1, label: 'Worse' },
                  { value: 0, label: 'Baseline' },
                  { value: 1, label: 'Better' },
                ]
          }
        />
      </CardContent>
    </Card>
  )
}
