'use client'

import { useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, UserPlus } from 'lucide-react'
import { Button, Card, Input, Label } from '@f0rge/ui'
import { PeerAvatar } from '@/components/people/peer-avatar'
import { PageHeader } from '@/components/layout/page-header'
import { PageShell } from '@/components/layout/page-shell'
import {
  useAcceptConnection,
  useConnections,
  useDeleteConnection,
  useSendConnectionRequest,
  useUserLookup,
} from '@/lib/api/hooks/social'
import { getErrorDetail } from '@f0rge/ui/api'
import { toast } from 'sonner'
import type { ConnectionItem } from '@/lib/api/types/social'

export default function ConnectionsClient() {
  const connections = useConnections()
  const [handle, setHandle] = useState('')
  const [error, setError] = useState<string | null>(null)
  const lookup = useUserLookup(handle)
  const send = useSendConnectionRequest()
  const accept = useAcceptConnection()
  const remove = useDeleteConnection()

  const onSend = async () => {
    setError(null)
    try {
      await send.mutateAsync(handle.trim().toLowerCase().replace(/^@/, ''))
      toast.success('Connection request sent')
      setHandle('')
    } catch (err) {
      setError(getErrorDetail(err, 'Could not send request'))
    }
  }

  const data = connections.data

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
        <Label htmlFor="add-handle">Add by @handle</Label>
        <div className="flex gap-2">
          <Input
            id="add-handle"
            value={handle}
            onChange={(e) => setHandle(e.target.value.toLowerCase().replace(/^@/, ''))}
            placeholder="their_handle"
            className="flex-1"
          />
          <Button type="button" onClick={onSend} disabled={send.isPending || handle.length < 3}>
            Send
          </Button>
        </div>
        {lookup.data && (
          <div className="flex items-center gap-3 rounded-lg border border-muted px-3 py-2">
            <PeerAvatar avatarDefaultIndex={lookup.data.avatar_default_index} />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">@{lookup.data.handle}</p>
              {lookup.data.display_name && (
                <p className="text-xs text-muted-foreground">{lookup.data.display_name}</p>
              )}
            </div>
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
      <PeerAvatar avatarDefaultIndex={item.user.avatar_default_index} />
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
