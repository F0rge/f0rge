'use client'

import { Zap } from 'lucide-react'
import type { Pattern } from '@/lib/checkin/patterns'
import { cn } from '@/lib/utils'

interface PatternBoxProps {
  pattern: Pattern
}

const SEVERITY_STYLES: Record<number, string> = {
  1: 'bg-emerald-50 border-emerald-100 text-emerald-900 dark:bg-emerald-950/30 dark:border-emerald-900 dark:text-emerald-100',
  2: 'bg-indigo-50 border-indigo-100 text-indigo-900 dark:bg-indigo-950/30 dark:border-indigo-900 dark:text-indigo-100',
  3: 'bg-amber-50 border-amber-200 text-amber-900 dark:bg-amber-950/30 dark:border-amber-900 dark:text-amber-100',
}

export function PatternBox({ pattern }: PatternBoxProps) {
  return (
    <div className={cn('mt-4 rounded-lg border p-3', SEVERITY_STYLES[pattern.severity])}>
      <div className="flex items-center gap-1.5 mb-1 text-xs font-semibold">
        <Zap className="size-3" />
        Pattern
      </div>
      <p className="text-[11px] leading-relaxed">{pattern.text}</p>
    </div>
  )
}
