'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { ClipboardCheck, Pill, CalendarDays, TrendingUp, Settings } from 'lucide-react'
import { cn } from '@/lib/utils'

const NAV_ITEMS = [
  { href: '/checkin', label: 'Today', icon: ClipboardCheck },
  { href: '/history', label: 'History', icon: CalendarDays },
  { href: '/treatments', label: 'Treatments', icon: Pill },
  { href: '/insights', label: 'Insights', icon: TrendingUp },
  { href: '/settings', label: 'Settings', icon: Settings },
] as const

export function BottomNav() {
  const pathname = usePathname()

  if (pathname.startsWith('/login')) return null

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-background pb-[env(safe-area-inset-bottom)]">
      <div className="mx-auto flex max-w-lg items-center justify-around">
        {NAV_ITEMS.map((item) => {
          const active = pathname.startsWith(item.href)
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex flex-1 flex-col items-center gap-0.5 py-2 text-xs transition-colors',
                active
                  ? 'text-primary'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <item.icon className="size-5" />
              {item.label}
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
