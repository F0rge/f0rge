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

function UnreadBadge({ count, className }: { count: number; className?: string }) {
  if (count <= 0) return null
  const label = count > 9 ? '9+' : String(count)
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-full bg-destructive font-semibold leading-none text-white ring-2 ring-background',
        label.length === 1 ? 'size-[18px] text-[10px]' : 'h-[18px] min-w-[18px] px-1 text-[10px]',
        className,
      )}
      aria-hidden
    >
      {label}
    </span>
  )
}

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
      <div className="relative inline-flex">
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-label={
            unreadCount > 0
              ? `Profile menu, ${unreadCount} unread in People`
              : 'Profile menu'
          }
          aria-haspopup="menu"
          aria-expanded={open}
          className="rounded-full shadow-sm transition-opacity hover:opacity-90"
        >
          <UserAvatar size="sm" />
        </button>
        <UnreadBadge count={unreadCount} className="pointer-events-none absolute -right-0.5 -top-0.5" />
      </div>
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
            className={cn(MENU_ITEM_CLASS, 'justify-between')}
            onClick={() => setOpen(false)}
            data-tour="people-menu"
          >
            <span className="flex items-center gap-2">
              <Users className="size-4 text-muted-foreground" />
              People
            </span>
            <UnreadBadge count={unreadCount} />
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
