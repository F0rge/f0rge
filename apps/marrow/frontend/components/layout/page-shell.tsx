import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '@f0rge/ui'

interface PageShellProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  className?: string
}

/** Shared page container — matches Check In's max-w-7xl + lg padding. */
export function PageShell({ children, className, ...props }: PageShellProps) {
  return (
    <div
      className={cn(
        'mx-auto w-full max-w-7xl px-5 pb-6 pt-[calc(20px+env(safe-area-inset-top))] lg:px-10 lg:pb-8',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  )
}
