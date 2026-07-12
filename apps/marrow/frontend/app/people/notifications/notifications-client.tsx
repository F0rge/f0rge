'use client'

import { useEffect } from 'react'
import Link from 'next/link'
import { ArrowLeft, Bell } from 'lucide-react'
import { Button, Card } from '@f0rge/ui'
import { PageHeader } from '@/components/layout/page-header'
import { PageShell } from '@/components/layout/page-shell'
import {
  notificationCopy,
  useMarkRead,
  useNotifications,
} from '@/lib/api/hooks/notifications'
import { formatDisplayDateTime } from '@f0rge/ui'

export default function NotificationsClient() {
  const notifications = useNotifications()
  const markRead = useMarkRead()

  useEffect(() => {
    markRead.mutate({ all: true })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <PageShell>
      <PageHeader
        leading={
          <Link
            href="/people"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
            Back
          </Link>
        }
        title={
          <div className="flex items-center gap-2">
            <Bell className="size-5 text-muted-foreground" />
            <h1 className="text-xl font-semibold tracking-tight">Notifications</h1>
          </div>
        }
        subtitle="Connection requests, invites, and meal tags."
      />

      <div className="mb-3 flex justify-end">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => markRead.mutate({ all: true })}
          disabled={markRead.isPending}
        >
          Mark all read
        </Button>
      </div>

      <Card className="overflow-hidden py-0">
        {notifications.isLoading && (
          <p className="px-4 py-6 text-sm text-muted-foreground">Loading...</p>
        )}
        {!notifications.isLoading && (notifications.data?.length ?? 0) === 0 && (
          <p className="px-4 py-6 text-sm text-muted-foreground">No notifications yet.</p>
        )}
        {notifications.data?.map((item) => (
          <div
            key={item.id}
            className="border-t border-muted px-4 py-3.5 first:border-t-0"
          >
            <p className="text-sm">{notificationCopy(item)}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {formatDisplayDateTime(item.created_at)}
            </p>
          </div>
        ))}
      </Card>
    </PageShell>
  )
}
