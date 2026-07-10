'use client'

/**
 * ProtocolCard — replaces the passive TreatmentBanner with an interactive,
 * gamified "Today's Protocol" card. Renders in the same top-of-board slot as
 * the old banner (NOT a reorderable card — card-order.ts is untouched).
 *
 * Dose-tracked treatments (doses_per_day set) get tappable pips wired to an
 * optimistic PUT. Non-dose treatments (e.g. a diet protocol) render as a
 * passive info row — the banner's "day N" information is preserved.
 */

import Link from 'next/link'
import { Check, Flame } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { useProtocol, useLogDose } from '@/lib/api/hooks'
import type { ProtocolItem } from '@/lib/api/types'
import { cn } from '@/lib/utils'
import { CheckinCardHeader } from '@/components/checkin/checkin-card-header'
import type { CheckinCardCollapseProps } from '@/components/checkin/checkin-card-collapse'

const RADIUS = 18
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

interface ProtocolCardProps extends CheckinCardCollapseProps {
  date: string
}

export function ProtocolCard({ date, collapsed, onToggleCollapsed }: ProtocolCardProps) {
  const { data: protocol } = useProtocol(date)
  const logDose = useLogDose(date)

  if (!protocol || protocol.items.length === 0) return null

  const { items, today, streak, best_streak } = protocol
  const isComplete = today.doses_planned > 0 && today.pct >= 1
  const offset = CIRCUMFERENCE * (1 - Math.min(today.pct, 1))

  function handleTap(item: ProtocolItem, n: number) {
    const next = n === item.doses_taken ? n - 1 : n
    logDose.mutate({ id: item.id, dosesTaken: next })
  }

  return (
    <Card className="col-span-12 h-full">
      <CheckinCardHeader
        title="Today's Protocol"
        collapsed={collapsed}
        onToggleCollapsed={onToggleCollapsed}
      />

      {!collapsed && (
      <CardContent className="p-0">
        <div className="flex items-center gap-4 border-b border-border px-4 py-3">
          <svg viewBox="0 0 40 40" className="size-10 shrink-0 -rotate-90">
            <circle
              cx="20" cy="20" r={RADIUS}
              fill="none" strokeWidth="4"
              className="stroke-muted"
            />
            <circle
              cx="20" cy="20" r={RADIUS}
              fill="none" strokeWidth="4" strokeLinecap="round"
              strokeDasharray={CIRCUMFERENCE}
              strokeDashoffset={offset}
              className={cn(
                'transition-[stroke-dashoffset] duration-500',
                isComplete ? 'stroke-emerald-600' : 'stroke-foreground',
              )}
            />
          </svg>

          <div className="min-w-0 flex-1">
            {isComplete ? (
              <p
                className={cn(
                  'flex items-center gap-1 text-sm font-medium text-emerald-600',
                  'motion-safe:animate-in motion-safe:zoom-in-90 motion-safe:duration-300',
                )}
              >
                <Check className="size-4" />
                Done for today
              </p>
            ) : (
              <p className="text-sm font-medium text-foreground">
                {today.doses_taken}/{today.doses_planned} doses
              </p>
            )}
            <div className="mt-0.5 flex items-center gap-3 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <Flame className="size-3.5" />
                {streak}-day streak
              </span>
              {best_streak > streak && <span>Best: {best_streak}</span>}
            </div>
          </div>
        </div>

        <ul className="divide-y divide-border">
          {items.map((item) =>
            item.doses_per_day === null ? (
              <InfoRow key={item.id} item={item} />
            ) : (
              <DoseRow key={item.id} item={item} onTap={(n) => handleTap(item, n)} />
            ),
          )}
        </ul>
        <div className="border-t border-border px-4 py-2.5">
          <Link
            href="/treatments"
            className="text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            View all treatments
          </Link>
        </div>
      </CardContent>
      )}
    </Card>
  )
}

function InfoRow({ item }: { item: ProtocolItem }) {
  return (
    <li className="flex items-center justify-between gap-3 px-4 py-3">
      <p className="truncate text-sm font-medium text-foreground">{item.name}</p>
      <span className="shrink-0 text-xs text-muted-foreground">day {item.day_num}</span>
    </li>
  )
}

function DoseRow({ item, onTap }: { item: ProtocolItem; onTap: (n: number) => void }) {
  const dosesPerDay = item.doses_per_day ?? 0

  return (
    <li className="flex items-center justify-between gap-3 px-4 py-3">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-foreground">{item.name}</p>
        {item.dose && <p className="truncate text-xs text-muted-foreground">{item.dose}</p>}
      </div>
      <div className="flex shrink-0 items-center gap-1.5" role="group" aria-label={`${item.name} doses`}>
        {Array.from({ length: dosesPerDay }, (_, i) => i + 1).map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => onTap(n)}
            aria-pressed={n <= item.doses_taken}
            aria-label={`Dose ${n} of ${dosesPerDay}`}
            className={cn(
              'size-5 rounded-full border-2 transition-colors',
              n <= item.doses_taken
                ? 'border-foreground bg-foreground'
                : 'border-muted-foreground/30 bg-transparent hover:border-muted-foreground/60',
            )}
          />
        ))}
      </div>
    </li>
  )
}
