'use client'

import Link from 'next/link'
import { Pill } from 'lucide-react'
import type { Treatment } from '@/lib/api/types'
import { getTreatmentDayNum } from '@/lib/checkin/treatment-day'

interface TreatmentBannerProps {
  treatments: Treatment[]
  checkinDate: string
}

export function TreatmentBanner({ treatments, checkinDate }: TreatmentBannerProps) {
  if (treatments.length === 0) return null

  return (
    <Link
      href="/treatments"
      className="col-span-12 flex items-center gap-2 rounded-xl border border-border bg-muted/50 px-4 py-3 transition-colors hover:bg-muted"
    >
      <Pill className="size-4 shrink-0 text-muted-foreground" />
      <p className="text-sm text-muted-foreground">
        <span className="font-medium text-foreground">Active treatments: </span>
        {treatments.map((t) => {
          const dayNum = getTreatmentDayNum(t.start_date, checkinDate)
          return `${t.name} (day ${dayNum})`
        }).join(', ')}
      </p>
    </Link>
  )
}
