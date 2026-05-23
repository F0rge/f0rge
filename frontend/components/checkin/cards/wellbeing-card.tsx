'use client'

import { Moon } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { ScaleInput } from '@/components/checkin/scale-input'

interface WellbeingCardProps {
  overall: number
  onOverallChange: (v: number) => void
  sleepQuality: number
  onSleepQualityChange: (v: number) => void
  stress: number
  onStressChange: (v: number) => void
  neuro: number
  onNeuroChange: (v: number) => void
}

export function WellbeingCard({
  overall, onOverallChange,
  sleepQuality, onSleepQualityChange,
  stress, onStressChange,
  neuro, onNeuroChange,
}: WellbeingCardProps) {
  return (
    <Card className="col-span-12 lg:col-span-4">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
          <Moon className="size-4" />
          Wellbeing
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <ScaleInput
          label="How was your day?"
          value={overall}
          onChange={(v) => onOverallChange(v as number)}
          options={[
            { value: 1, label: 'Very Poor' },
            { value: 2, label: 'Standard' },
            { value: 3, label: 'Very Good' },
          ]}
        />
        <ScaleInput
          label="Sleep quality (last night)"
          value={sleepQuality}
          onChange={(v) => onSleepQualityChange(v as number)}
          options={[
            { value: 1, label: 'Poor' },
            { value: 2, label: 'OK' },
            { value: 3, label: 'Good' },
          ]}
        />
        <ScaleInput
          label="Stress level"
          value={stress}
          onChange={(v) => onStressChange(v as number)}
          options={[
            { value: 1, label: 'Low' },
            { value: 2, label: 'Medium' },
            { value: 3, label: 'High' },
          ]}
        />
        <ScaleInput
          label="Neuro symptoms"
          value={neuro}
          onChange={(v) => onNeuroChange(v as number)}
          options={[
            { value: -1, label: 'Worse' },
            { value: 0, label: 'Baseline' },
            { value: 1, label: 'Better' },
          ]}
        />
      </CardContent>
    </Card>
  )
}
