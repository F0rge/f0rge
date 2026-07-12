'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { LogOut, SlidersHorizontal, UserRound, Users } from 'lucide-react'
import { UserAvatar } from '@/components/account/user-avatar'
import { ThemeToggle } from '@/components/layout/theme-toggle'
import { useLogout, useUnreadCount } from '@/lib/api/hooks'
import { handleMutationError } from '@f0rge/ui/api'
import { cn } from '@f0rge/ui'

const MENU_ITEM_CLASS =
  'flex w-full items-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-sm text-foreground transition-colors hover:bg-muted'

export function ProfileMenu() {
  const pathname = usePathname()
  const router = useRouter()
  const logout = useLogout()
  const unread = useUnreadCount()
  const unreadCount = unread.data?.count ?? 0
  const [open, setOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  const handleLogout = async () => {
    try {
      await logout.mutateAsync()
      setOpen(false)
      router.replace('/login')
    } catch (err) {
      handleMutationError(err, 'Could not log out')
    }
  }

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

  return (
    <div ref={menuRef} className="relative" data-tour="profile-menu">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-label="Profile menu"
        aria-haspopup="menu"
        aria-expanded={open}
        className={cn(
          'relative overflow-hidden rounded-full shadow-sm transition-opacity hover:opacity-90',
        )}
      >
        <UserAvatar size="sm" />
        {unreadCount > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex min-h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-semibold text-primary-foreground">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-2 min-w-[10rem] rounded-xl border border-border bg-background p-1 shadow-lg"
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
            href="/people"
            role="menuitem"
            className={MENU_ITEM_CLASS}
            onClick={() => setOpen(false)}
            data-tour="people-menu"
          >
            <Users className="size-4 text-muted-foreground" />
            People
          </Link>
          <Link
            href="/customize"
            role="menuitem"
            className={MENU_ITEM_CLASS}
            onClick={() => setOpen(false)}
          >
            <SlidersHorizontal className="size-4 text-muted-foreground" />
            Customize
          </Link>
          <button
            type="button"
            role="menuitem"
            className={MENU_ITEM_CLASS}
            onClick={handleLogout}
            disabled={logout.isPending}
          >
            <LogOut className="size-4 text-muted-foreground" />
            Log out
          </button>
          <div className="mt-1 border-t border-border pt-1">
            <ThemeToggle />
          </div>
        </div>
      )}
    </div>
  )
}
