'use client'

import { useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, UserPlus } from 'lucide-react'
import { Button, Card, Input, Label, useDebouncedValue } from '@f0rge/ui'
import { PeerAvatar } from '@/components/people/peer-avatar'
import { PageHeader } from '@/components/layout/page-header'
import { PageShell } from '@/components/layout/page-shell'
import {
  useAcceptConnection,
  useConnections,
  useDeleteConnection,
  useSendConnectionRequest,
  useUserSearch,
} from '@/lib/api/hooks/social'
import { getErrorDetail } from '@f0rge/ui/api'
import { toast } from 'sonner'
import type { ConnectionItem, ConnectionStatus, UserSearchItem } from '@/lib/api/types/social'

export default function ConnectionsClient() {
  const connections = useConnections()
  const [handle, setHandle] = useState('')
  const [error, setError] = useState<string | null>(null)
  const debouncedQuery = useDebouncedValue(handle, 300)
  const search = useUserSearch(debouncedQuery)
  const send = useSendConnectionRequest()
  const accept = useAcceptConnection()
  const remove = useDeleteConnection()

  const onSend = async (targetHandle: string) => {
    setError(null)
    try {
      await send.mutateAsync(targetHandle)
      toast.success('Connection request sent')
    } catch (err) {
      setError(getErrorDetail(err, 'Could not send request'))
    }
  }

  const data = connections.data
  const showResults = debouncedQuery.trim().length >= 3

  return (
    <PageShell>
      <PageHeader
        leading={
          <Link href="/people" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="size-4" />
            Back
          </Link>
        }
        title={
          <div className="flex items-center gap-2">
            <UserPlus className="size-5 text-muted-foreground" />
            <h1 className="text-xl font-semibold tracking-tight">Connections</h1>
          </div>
        }
        subtitle="Connect with people you want to tag on meals."
      />

      <Card className="space-y-3 p-4">
        <Label htmlFor="add-handle">Find by @handle</Label>
        <Input
          id="add-handle"
          value={handle}
          onChange={(e) => {
            setHandle(e.target.value.toLowerCase().replace(/^@/, ''))
            setError(null)
          }}
          placeholder="Search handle prefix (min 3 chars)"
        />
        {showResults && (
          <div className="space-y-2">
            {search.isLoading && (
              <p className="text-sm text-muted-foreground">Searching...</p>
            )}
            {search.isError && (
              <p className="text-sm text-destructive">Could not search users.</p>
            )}
            {search.data?.users.length === 0 && !search.isLoading && (
              <p className="text-sm text-muted-foreground">No users match that prefix.</p>
            )}
            {search.data?.users.map((user) => (
              <SearchResultRow
                key={user.handle}
                user={user}
                sendPending={send.isPending && send.variables === user.handle}
                acceptPending={accept.isPending}
                removePending={remove.isPending}
                onSend={() => void onSend(user.handle)}
                onAccept={() => {
                  if (user.connection_id) accept.mutate(user.connection_id)
                }}
                onCancelOutgoing={() => {
                  if (user.connection_id) remove.mutate(user.connection_id)
                }}
              />
            ))}
          </div>
        )}
        {error && <p className="text-sm text-destructive">{error}</p>}
      </Card>

      <Section title="Incoming requests">
        {data?.pending_incoming.map((item) => (
          <ConnectionRow
            key={item.id}
            item={item}
            actions={
              <>
                <Button size="sm" onClick={() => accept.mutate(item.id)} disabled={accept.isPending}>
                  Accept
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => remove.mutate(item.id)}
                  disabled={remove.isPending}
                >
                  Decline
                </Button>
              </>
            }
          />
        ))}
        {(data?.pending_incoming.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No incoming requests.</p>
        )}
      </Section>

      <Section title="Outgoing">
        {data?.pending_outgoing.map((item) => (
          <ConnectionRow
            key={item.id}
            item={item}
            actions={
              <Button size="sm" variant="outline" onClick={() => remove.mutate(item.id)} disabled={remove.isPending}>
                Cancel
              </Button>
            }
          />
        ))}
        {(data?.pending_outgoing.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No pending outgoing requests.</p>
        )}
      </Section>

      <Section title="Connected">
        {data?.accepted.map((item) => (
          <ConnectionRow
            key={item.id}
            item={item}
            actions={
              <Button size="sm" variant="outline" onClick={() => remove.mutate(item.id)} disabled={remove.isPending}>
                Remove
              </Button>
            }
          />
        ))}
        {(data?.accepted.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No connections yet.</p>
        )}
      </Section>
    </PageShell>
  )
}

function SearchResultRow({
  user,
  sendPending,
  acceptPending,
  removePending,
  onSend,
  onAccept,
  onCancelOutgoing,
}: {
  user: UserSearchItem
  sendPending: boolean
  acceptPending: boolean
  removePending: boolean
  onSend: () => void
  onAccept: () => void
  onCancelOutgoing: () => void
}) {
  const action = statusAction(user.connection_status, {
    sendPending,
    acceptPending,
    removePending,
    onSend,
    onAccept,
    onCancelOutgoing,
  })

  return (
    <div className="flex items-center gap-3 rounded-lg border border-muted px-3 py-2">
      <PeerAvatar
        handle={user.handle}
        avatarDefaultIndex={user.avatar_default_index}
        hasCustomAvatar={user.has_custom_avatar}
      />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">@{user.handle}</p>
        {user.display_name && (
          <p className="text-xs text-muted-foreground">{user.display_name}</p>
        )}
      </div>
      <div className="shrink-0">{action}</div>
    </div>
  )
}

function statusAction(
  status: ConnectionStatus,
  opts: {
    sendPending: boolean
    acceptPending: boolean
    removePending: boolean
    onSend: () => void
    onAccept: () => void
    onCancelOutgoing: () => void
  },
): React.ReactNode {
  switch (status) {
    case 'connected':
      return <span className="text-xs font-medium text-muted-foreground">Connected</span>
    case 'pending_outgoing':
      return (
        <Button size="sm" variant="outline" onClick={opts.onCancelOutgoing} disabled={opts.removePending}>
          Pending
        </Button>
      )
    case 'pending_incoming':
      return (
        <Button size="sm" onClick={opts.onAccept} disabled={opts.acceptPending}>
          Accept
        </Button>
      )
    default:
      return (
        <Button size="sm" onClick={opts.onSend} disabled={opts.sendPending}>
          Send
        </Button>
      )
  }
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-6 space-y-3">
      <h2 className="text-sm font-semibold">{title}</h2>
      <Card className="space-y-2 p-3">{children}</Card>
    </section>
  )
}

function ConnectionRow({
  item,
  actions,
}: {
  item: ConnectionItem
  actions: React.ReactNode
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-muted px-3 py-2">
      <PeerAvatar
        handle={item.user.handle}
        avatarDefaultIndex={item.user.avatar_default_index}
        hasCustomAvatar={item.user.has_custom_avatar}
      />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">@{item.user.handle}</p>
        {item.user.display_name && (
          <p className="text-xs text-muted-foreground">{item.user.display_name}</p>
        )}
      </div>
      <div className="flex shrink-0 gap-2">{actions}</div>
    </div>
  )
}
