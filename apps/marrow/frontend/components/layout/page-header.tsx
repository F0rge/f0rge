'use client'

import type { ReactNode, Ref } from 'react'
import { ProfileMenu } from '@/components/layout/profile-menu'
import { cn } from '@f0rge/ui'

interface PageHeaderProps {
  title: ReactNode
  subtitle?: ReactNode
  leading?: ReactNode
  actions?: ReactNode
  layout?: 'row' | 'responsive'
  className?: string
  headerRef?: Ref<HTMLDivElement>
  'data-tour'?: string
}

const TITLE_CLASS = 'text-xl font-semibold tracking-tight'

export function PageHeader({
  title,
  subtitle,
  leading,
  actions,
  layout = 'row',
  className,
  headerRef,
  'data-tour': dataTour,
}: PageHeaderProps) {
  const isResponsive = layout === 'responsive'

  return (
    <div ref={headerRef} className={cn('mb-6', className)} data-tour={dataTour}>
      {leading ? <div className="mb-3">{leading}</div> : null}
      <div
        className={cn(
          'flex gap-3',
          isResponsive
            ? 'flex-col sm:flex-row sm:items-center sm:justify-between'
            : 'items-start justify-between',
        )}
      >
        <div className="min-w-0 flex-1">
          {typeof title === 'string' ? <h1 className={TITLE_CLASS}>{title}</h1> : title}
          {subtitle != null &&
            (typeof subtitle === 'string' ? (
              <p className="text-sm text-muted-foreground">{subtitle}</p>
            ) : (
              subtitle
            ))}
        </div>
        <div
          className={cn(
            'flex shrink-0 items-center gap-2',
            isResponsive && 'self-end sm:self-auto',
          )}
        >
          {actions}
          <ProfileMenu />
        </div>
      </div>
    </div>
  )
}
