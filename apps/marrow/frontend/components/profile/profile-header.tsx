'use client'

import Link from 'next/link'
import { Bell, Flame, Menu } from 'lucide-react'
import { toast } from 'sonner'
import { UserAvatar } from '@/components/account/user-avatar'
import {
  useAccount,
  useConnections,
  useEntryStats,
  useGroups,
  useUnreadCount,
} from '@/lib/api/hooks'

function StatLink({ href, value, label }: { href: string; value: number; label: string }) {
  return (
    <Link href={href} className="flex-1 text-center">
      <span className="block text-[17px] font-bold tabular-nums">{value}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
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
  const streak = stats.data?.current_streak_days ?? 0
  const since = data?.created_at
    ? new Date(data.created_at).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' })
    : null

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

      <div className="mt-4 flex items-center gap-5">
        <UserAvatar size="lg" />
        <div className="flex flex-1">
          <StatLink href="/history" value={stats.data?.total_checkins ?? 0} label="Check-ins" />
          <StatLink
            href="/people/connections"
            value={connections.data?.accepted.length ?? 0}
            label="Connections"
          />
          <StatLink
            href="/people/groups"
            value={groups.data?.filter((g) => g.my_status === 'joined').length ?? 0}
            label="Groups"
          />
        </div>
      </div>

      <div className="mt-3">
        {data?.display_name && <p className="text-sm font-semibold">{data.display_name}</p>}
        <p className="mt-0.5 flex items-center gap-1.5 text-[13px] text-muted-foreground">
          {streak > 0 && (
            <>
              <Flame className="size-[13px]" aria-hidden />
              {streak}-day streak
              {since && <span aria-hidden>·</span>}
            </>
          )}
          {since && <>tracking since {since}</>}
        </p>
      </div>

      <div className="mt-4 flex gap-2">
        <Link
          href="/account"
          className="flex-1 rounded-lg bg-muted py-2 text-center text-[13px] font-semibold transition-colors hover:bg-muted/80"
        >
          Edit profile
        </Link>
        <button
          type="button"
          onClick={handleShare}
          className="flex-1 rounded-lg bg-muted py-2 text-center text-[13px] font-semibold transition-colors hover:bg-muted/80"
        >
          Share profile
        </button>
      </div>
    </header>
  )
}
