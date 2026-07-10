'use client'

import { Card, CardContent } from '@/components/ui/card'
import { SupplementPicker } from '@/components/checkin/supplement-picker'
import { CheckinCardHeader } from '@/components/checkin/checkin-card-header'
import type { CheckinCardCollapseProps } from '@/components/checkin/checkin-card-collapse'

interface SupplementsCardProps extends CheckinCardCollapseProps {
  value: string
  onChange: (v: string) => void
  onTouched: () => void
}

export function SupplementsCard({
  value,
  onChange,
  onTouched,
  collapsed,
  onToggleCollapsed,
}: SupplementsCardProps) {
  return (
    <Card className="h-full">
      <CheckinCardHeader
        title="Supplements"
        tier="catalog"
        collapsed={collapsed}
        onToggleCollapsed={onToggleCollapsed}
      />
      {!collapsed && (
        <CardContent>
          <SupplementPicker
            value={value}
            onChange={(v) => {
              onTouched()
              onChange(v)
            }}
          />
        </CardContent>
      )}
    </Card>
  )
}
