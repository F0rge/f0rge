'use client'

import { Card, CardContent } from '@f0rge/ui'
import { SymptomPicker } from '@/components/checkin/symptom-picker'
import { CheckinCardHeader } from '@/components/checkin/checkin-card-header'
import type { CheckinCardCollapseProps } from '@/components/checkin/checkin-card-collapse'
import type { SymptomEvent } from '@/lib/api/types'

interface SymptomsCardProps extends CheckinCardCollapseProps {
  value: Record<string, number>
  onChange: (v: Record<string, number>) => void
  events: SymptomEvent[]
  onEventsChange: (v: SymptomEvent[]) => void
}

export function SymptomsCard({
  value,
  onChange,
  events,
  onEventsChange,
  collapsed,
  onToggleCollapsed,
}: SymptomsCardProps) {
  return (
    <Card className="h-full">
      <CheckinCardHeader
        title="Symptoms today"
        tier="custom"
        collapsed={collapsed}
        onToggleCollapsed={onToggleCollapsed}
      />
      {!collapsed && (
        <CardContent>
          <SymptomPicker
            value={value}
            onChange={onChange}
            events={events}
            onEventsChange={onEventsChange}
          />
        </CardContent>
      )}
    </Card>
  )
}
