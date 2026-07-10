'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { SlidersHorizontal, UserRound } from 'lucide-react'
import { useAccount } from '@/lib/api/hooks'
import { getAccountInitials } from '@/lib/account-initials'
import { cn } from '@/lib/utils'

const MENU_ITEM_CLASS =
  'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-foreground transition-colors hover:bg-muted'

export function ProfileMenu() {
  const pathname = usePathname()
  const [open, setOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const account = useAccount()

  useEffect(() => {
    setOpen(false)
  }, [pathname])

  useEffect(() => {
    if (!open) return
    const handleClick = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handleClick)
      document.removeEventListener('keydown', handleKey)
    }
  }, [open])

  if (pathname.startsWith('/login') || pathname.startsWith('/signup')) return null

  const initials = account.data ? getAccountInitials(account.data) : '…'

  return (
    <div
      ref={menuRef}
      className="fixed top-[calc(16px+env(safe-area-inset-top))] right-[calc(16px+env(safe-area-inset-right))] z-50"
    >
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-label="Profile menu"
        aria-haspopup="menu"
        aria-expanded={open}
        className={cn(
          'flex size-9 items-center justify-center rounded-full border border-border',
          'bg-background/88 text-xs font-semibold shadow-sm backdrop-blur-sm',
          'transition-colors hover:bg-muted',
        )}
      >
        {initials}
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 mt-2 min-w-[188px] rounded-xl border border-border bg-background p-1 shadow-lg"
        >
          <Link
            href="/account"
            role="menuitem"
            className={MENU_ITEM_CLASS}
            onClick={() => setOpen(false)}
          >
            <UserRound className="size-4 text-muted-foreground" />
            Account
          </Link>
          <Link
            href="/customize"
            role="menuitem"
            className={MENU_ITEM_CLASS}
            onClick={() => setOpen(false)}
          >
            <SlidersHorizontal className="size-4 text-muted-foreground" />
            Customize check-in
          </Link>
        </div>
      )}
    </div>
  )
}
