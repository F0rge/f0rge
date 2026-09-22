import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@f0rge/ui'

interface SettingsCardProps {
  icon?: LucideIcon
  iconClassName?: string
  title: string
  children: ReactNode
  className?: string
}

// Shared card shell for every /settings section: icon + title header, then
// section-specific content. Matches the pre-refactor hand-rolled markup
// exactly (`rounded-xl border border-border p-4 space-y-3`).
export function SettingsCard({
  icon: Icon,
  iconClassName,
  title,
  children,
  className,
}: SettingsCardProps) {
  return (
    <div className={cn('h-full space-y-4 rounded-[var(--radius)] border border-border bg-card p-5', className)}>
      <div className="flex items-center gap-2">
        {Icon && <Icon className={`size-5 text-muted-foreground ${iconClassName ?? ''}`} />}
        <h2 className="text-sm font-medium text-muted-foreground">{title}</h2>
      </div>
      {children}
    </div>
  )
}
