'use client'

import type { Lab } from '@/lib/api/types'
import { Badge, cn, formatDisplayDate, Item, ItemActions, ItemContent, ItemDescription, ItemHeader, ItemTitle } from '@f0rge/ui'
import { labTypeClass, statusPill } from '@/lib/ui/status'

interface LabCardProps {
  lab: Lab
  onClick: () => void
  selected?: boolean
}

const TYPE_CLASSES = labTypeClass

export function LabCard({ lab, onClick, selected = false }: LabCardProps) {
  const abnormalCount = lab.markers.filter(
    (m) => m.flag === 'low' || m.flag === 'high' || m.flag === 'abnormal',
  ).length

  return (
    <Item
      variant="outline"
      className={cn(
        'w-full cursor-pointer rounded-xl bg-card transition-colors hover:bg-muted/50',
        selected ? 'border-primary ring-1 ring-primary/30' : 'border-border',
      )}
      render={<button type="button" onClick={onClick} />}
    >
      <ItemContent>
        <ItemHeader>
          <ItemTitle className="flex flex-wrap items-center gap-1.5">
            <span className="truncate">{lab.name}</span>
            <Badge variant="secondary" className={TYPE_CLASSES[lab.type] ?? TYPE_CLASSES.other}>
              {lab.type}
            </Badge>
          </ItemTitle>
          <ItemActions className="shrink-0 flex-col items-end gap-1">
            <span className="text-xs text-muted-foreground">
              {lab.markers.length} marker{lab.markers.length !== 1 ? 's' : ''}
            </span>
            {abnormalCount > 0 && (
              <Badge variant="secondary" className={statusPill.destructive}>
                {abnormalCount} abnormal
              </Badge>
            )}
            {lab.review_status === 'needs_review' && (
              <Badge variant="secondary" className={statusPill.warn}>
                review
              </Badge>
            )}
          </ItemActions>
        </ItemHeader>
        <ItemDescription>
          {formatDisplayDate(lab.lab_date)}
          {lab.lab_location ? ` · ${lab.lab_location}` : ''}
        </ItemDescription>
      </ItemContent>
    </Item>
  )
}
