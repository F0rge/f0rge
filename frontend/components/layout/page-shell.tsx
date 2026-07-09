import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface PageShellProps {
  children: ReactNode
  className?: string
}

/** Shared page container — matches Check In's max-w-7xl + lg padding. */
export function PageShell({ children, className }: PageShellProps) {
  return (
    <div className={cn('mx-auto w-full max-w-7xl p-4 lg:px-8', className)}>
      {children}
    </div>
  )
}
