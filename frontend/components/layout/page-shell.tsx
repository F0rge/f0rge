import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface PageShellProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  className?: string
}

/** Shared page container — matches Check In's max-w-7xl + lg padding. */
export function PageShell({ children, className, ...props }: PageShellProps) {
  return (
    <div className={cn('mx-auto w-full max-w-7xl p-4 lg:px-8', className)} {...props}>
      {children}
    </div>
  )
}
