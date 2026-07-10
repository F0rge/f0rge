import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

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
    <div className={cn('h-full rounded-xl border border-border p-4 space-y-3', className)}>
      <div className="flex items-center gap-2">
        {Icon && <Icon className={`size-5 ${iconClassName ?? ''}`} />}
        <h2 className="font-semibold">{title}</h2>
      </div>
      {children}
    </div>
  )
}
