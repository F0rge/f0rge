'use client'

// TODO(#79): This card's body will be replaced by the full Trackers feature
// (user-defined counters, backend-backed tracker_log table). For now it
// renders the four existing hardcoded fields so they aren't lost during the
// cards refactor.

import { BarChart2 } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Stepper } from '@/components/ui/stepper'
import { BinaryInput } from '@/components/checkin/binary-input'

interface TrackersCardProps {
  alcoholUnits: number
  onAlcoholUnitsChange: (v: number) => void
  caffeineServings: number
  onCaffeineServingsChange: (v: number) => void
  sick: boolean
  onSickChange: (v: boolean) => void
  hotShower: boolean
  onHotShowerChange: (v: boolean) => void
}

export function TrackersCard({
  alcoholUnits, onAlcoholUnitsChange,
  caffeineServings, onCaffeineServingsChange,
  sick, onSickChange,
  hotShower, onHotShowerChange,
}: TrackersCardProps) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
          <BarChart2 className="size-4" />
          Daily counters
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex justify-around rounded-xl border border-border bg-background p-4">
          <Stepper
            value={alcoholUnits}
            onChange={onAlcoholUnitsChange}
            min={0}
            max={10}
            label="Alcohol units"
            tooltip="1 unit = small glass of wine / half a beer"
          />
          <Stepper
            value={caffeineServings}
            onChange={onCaffeineServingsChange}
            min={0}
            max={10}
            label="Caffeine servings"
            tooltip="1 serving = one coffee / one strong tea"
          />
        </div>

        <BinaryInput
          label="Sick / cold?"
          value={sick}
          onChange={onSickChange}
          trueLabel="Yes"
          falseLabel="No"
        />

        <BinaryInput
          label="Full-body hot shower today?"
          value={hotShower}
          onChange={onHotShowerChange}
          trueLabel="Yes"
          falseLabel="No"
        />
      </CardContent>
    </Card>
  )
}
