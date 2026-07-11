'use client'

import { Card, CardContent } from '@/components/ui/card'
import { SymptomPicker } from '@/components/checkin/symptom-picker'
import { CheckinCardHeader } from '@/components/checkin/checkin-card-header'
import type { CheckinCardCollapseProps } from '@/components/checkin/checkin-card-collapse'

interface SymptomsCardProps extends CheckinCardCollapseProps {
  value: Record<string, number>
  onChange: (v: Record<string, number>) => void
}

export function SymptomsCard({
  value,
  onChange,
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
          <SymptomPicker value={value} onChange={onChange} />
        </CardContent>
      )}
    </Card>
  )
}
