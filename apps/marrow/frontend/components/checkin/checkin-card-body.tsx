'use client'

import type { ReactNode } from 'react'
import { CardContent, Frame, FramePanel, cn } from '@f0rge/ui'

interface CheckinCardBodyProps {
  children: ReactNode
  className?: string
  panelClassName?: string
}

/** Card content wrapped in a ReUI Frame panel for check-in sections. */
export function CheckinCardBody({ children, className, panelClassName }: CheckinCardBodyProps) {
  return (
    <CardContent className={cn('pt-0', className)}>
      <Frame spacing="sm" variant="ghost" className="w-full">
        <FramePanel className={cn('space-y-5', panelClassName)}>{children}</FramePanel>
      </Frame>
    </CardContent>
  )
}
