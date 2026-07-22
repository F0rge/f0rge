'use client'

import Link from 'next/link'
import { Bell, ClipboardCheck, Menu, Share, Users, UsersRound, type LucideIcon } from 'lucide-react'
import { toast } from 'sonner'
import { StreakRing } from '@/components/profile/streak-ring'
import {
  useAccount,
  useConnections,
  useEntryStats,
  useGroups,
  useUnreadCount,
} from '@/lib/api/hooks'

function StatChip({
  href,
  icon: Icon,
  value,
  label,
}: {
  href: string
  icon: LucideIcon
  value: number
  label: string
}) {
  return (
    <Link
      href={href}
      className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-1 text-[11px] font-semibold text-muted-foreground transition-colors hover:bg-muted/80"
    >
      <Icon className="size-[11px]" aria-hidden />
      <b className="font-bold tabular-nums text-foreground">{value}</b>
      {label}
    </Link>
  )
}

export function ProfileHeader() {
  const account = useAccount()
  const stats = useEntryStats()
  const connections = useConnections()
  const groups = useGroups()
  const unreadCount = useUnreadCount().data?.count ?? 0

  const data = account.data
  const handle = data?.handle
  const name = data?.display_name ?? handle
  const since = data?.created_at
    ? new Date(data.created_at).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' })
    : null
  // Missing segments drop out instead of printing "null"; the separator goes with them.
  const subline = [handle && `@${handle}`, since && `tracking since ${since}`]
    .filter(Boolean)
    .join(' · ')

  const handleShare = async () => {
    const text = handle ? `@${handle} on Marrow` : 'Find me on Marrow'
    if (navigator.share) {
      // User closing the share sheet rejects — that's not an error worth surfacing.
      await navigator.share({ text }).catch(() => undefined)
      return
    }
    await navigator.clipboard.writeText(text)
    toast.success(handle ? `Copied @${handle}` : 'Copied')
  }

  return (
    <header data-tour="profile-header">
      <div className="flex items-center justify-between">
        <h1 className="text-[17px] font-bold tracking-tight">
          {handle ? `@${handle}` : (data?.display_name ?? 'Profile')}
        </h1>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={handleShare}
            aria-label="Share profile"
            className="flex size-9 items-center justify-center rounded-lg transition-colors hover:bg-muted"
          >
            <Share className="size-[22px]" />
          </button>
          <Link
            href="/people/notifications"
            aria-label={
              unreadCount > 0 ? `Notifications, ${unreadCount} unread` : 'Notifications'
            }
            className="relative flex size-9 items-center justify-center rounded-lg transition-colors hover:bg-muted"
          >
            <Bell className="size-[22px]" />
            {unreadCount > 0 && (
              <span className="absolute right-0 top-0 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold leading-none text-white ring-2 ring-background">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </Link>
          <Link
            href="/settings"
            aria-label="Settings and activity"
            className="flex size-9 items-center justify-center rounded-lg transition-colors hover:bg-muted"
          >
            <Menu className="size-[22px]" />
          </Link>
        </div>
      </div>

      <div className="mt-4 flex items-center gap-4">
        <StreakRing streak={stats.data?.current_streak_days ?? 0} />
        <div className="min-w-0 flex-1">
          {name && <p className="truncate text-base font-bold">{name}</p>}
          {subline && <p className="mt-0.5 text-[12.5px] text-muted-foreground">{subline}</p>}
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            <StatChip
              href="/history"
              icon={ClipboardCheck}
              value={stats.data?.total_checkins ?? 0}
              label="Check-ins"
            />
            <StatChip
              href="/people/connections"
              icon={Users}
              value={connections.data?.accepted.length ?? 0}
              label="Connections"
            />
            <StatChip
              href="/people/groups"
              icon={UsersRound}
              value={groups.data?.filter((g) => g.my_status === 'joined').length ?? 0}
              label="Groups"
            />
          </div>
        </div>
      </div>

      <Link
        href="/account"
        className="mt-4 block rounded-lg bg-muted py-2 text-center text-[13px] font-semibold transition-colors hover:bg-muted/80"
      >
        Edit profile
      </Link>
    </header>
  )
}
