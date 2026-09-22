'use client'

import Link from 'next/link'
import { CalendarDays } from 'lucide-react'
import type { ReactNode, Ref } from 'react'
import { PageHeader } from '@/components/layout/page-header'

export function formatCheckinDisplayDate(dateStr: string): string {
  const date = new Date(dateStr + 'T00:00:00')
  return date.toLocaleDateString('en-GB', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

interface CheckinPageHeaderProps {
  date: string
  headerRef?: Ref<HTMLDivElement>
  actions?: ReactNode
}

/** Shared check-in framing: title · date, with History wayfinding. */
export function CheckinPageHeader({ date, headerRef, actions }: CheckinPageHeaderProps) {
  return (
    <PageHeader
      headerRef={headerRef}
      data-tour="checkin-header"
      data-testid="checkin-header"
      leading={
        <Link
          href="/history"
          className="inline-flex min-h-[44px] items-center gap-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          <CalendarDays className="size-4 shrink-0" aria-hidden />
          History
        </Link>
      }
      title={
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Check-in{' '}
          <span className="font-normal text-muted-foreground">
            · {formatCheckinDisplayDate(date)}
          </span>
        </h1>
      }
      actions={actions}
    />
  )
}
