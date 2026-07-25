'use client'

import { ChevronDown } from 'lucide-react'
import { cn } from '@f0rge/ui'
import type { SignalsMirror } from '@/lib/api/types/signals'

interface Props {
  mirrors: SignalsMirror[]
}

export function SetAside({ mirrors }: Props) {
  if (mirrors.length === 0) return null

  return (
    <details className="group rounded-xl bg-card ring-1 ring-foreground/10">
      <summary
        className={cn(
          'flex cursor-pointer list-none items-center justify-between gap-2 px-3 py-2.5 text-sm font-medium',
          '[&::-webkit-details-marker]:hidden',
        )}
      >
        <span>Set aside ({mirrors.length})</span>
        <ChevronDown
          className={cn(
            'size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180 motion-reduce:transition-none',
          )}
        />
      </summary>
      <ul className="space-y-2 border-t border-border px-3 py-2">
        {mirrors.map((m) => (
          <li key={m.feature} className="text-xs">
            <p className="font-medium">{m.label}</p>
            <p className="text-muted-foreground">
              ρ {m.rho != null ? m.rho.toFixed(2) : '—'} · n={m.n}
            </p>
            <p className="text-muted-foreground">{m.reason}</p>
          </li>
        ))}
      </ul>
    </details>
  )
}
