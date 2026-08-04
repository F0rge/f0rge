'use client'

import { BottomNav } from '@/components/bottom-nav'
import { useKeyboardOpen } from '@/hooks/use-keyboard-open'
import { cn } from '@f0rge/ui'

interface AppShellProps {
  children: React.ReactNode
}

export function AppShell({ children }: AppShellProps) {
  const keyboardOpen = useKeyboardOpen()

  return (
    <>
      <div
        className={cn(
          'flex-1',
          !keyboardOpen && 'pb-[calc(84px+env(safe-area-inset-bottom))]',
        )}
      >
        {children}
      </div>
      <BottomNav />
    </>
  )
}
