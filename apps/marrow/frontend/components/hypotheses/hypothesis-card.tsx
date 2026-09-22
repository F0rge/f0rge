'use client'

import { cn } from '@f0rge/ui'
import { statusPill } from '@/lib/ui/status'
import type { Hypothesis, HypothesisStatus } from '@/lib/api/types'

const STATUS_LABEL: Record<HypothesisStatus, string> = {
  live: 'Live',
  weakening: 'Weakening',
  killed: 'Killed',
  parked: 'Parked',
}

const STATUS_PILL: Record<HypothesisStatus, string> = {
  live: statusPill.ok,
  weakening: statusPill.warn,
  killed: statusPill.muted,
  parked: statusPill.info,
}

interface HypothesisCardProps {
  hypothesis: Hypothesis
  onStatusChange: (status: HypothesisStatus) => void
}

export function HypothesisCard({ hypothesis, onStatusChange }: HypothesisCardProps) {
  return (
    <article className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-sm font-medium">{hypothesis.title}</h3>
            {hypothesis.layer != null && (
              <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-semibold', statusPill.info)}>
                Layer {hypothesis.layer}
              </span>
            )}
          </div>
          <p className="mt-0.5 font-mono text-[11px] text-muted-foreground">{hypothesis.slug}</p>
        </div>
        <label className="sr-only" htmlFor={`status-${hypothesis.id}`}>
          Status
        </label>
        <select
          id={`status-${hypothesis.id}`}
          className={cn(
            'shrink-0 rounded-full border-0 px-2 py-0.5 text-xs font-medium',
            STATUS_PILL[hypothesis.status],
          )}
          value={hypothesis.status}
          onChange={(event) => onStatusChange(event.target.value as HypothesisStatus)}
        >
          {(Object.keys(STATUS_LABEL) as HypothesisStatus[]).map((status) => (
            <option key={status} value={status}>
              {STATUS_LABEL[status]}
            </option>
          ))}
        </select>
      </div>
      {hypothesis.kill_test && (
        <p className="mt-3 text-sm text-foreground">
          <span className="font-semibold text-muted-foreground">Kill-test. </span>
          {hypothesis.kill_test}
        </p>
      )}
      {hypothesis.last_evidence && (
        <p className="mt-2 text-sm text-muted-foreground">
          <span className="font-semibold">Last note. </span>
          {hypothesis.last_evidence}
        </p>
      )}
      {hypothesis.next_move && (
        <p className="mt-2 text-sm text-muted-foreground">
          <span className="font-semibold">Next. </span>
          {hypothesis.next_move}
        </p>
      )}
      {hypothesis.cite && (
        <p className="mt-2 text-xs text-muted-foreground">Cite: {hypothesis.cite}</p>
      )}
    </article>
  )
}
