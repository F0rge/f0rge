'use client'

import { useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, UsersRound } from 'lucide-react'
import { Badge, Button, Card, Input, Label } from '@f0rge/ui'
import { FetchError } from '@f0rge/ui'
import { PageHeader } from '@/components/layout/page-header'
import { PageShell } from '@/components/layout/page-shell'
import { useAccount } from '@/lib/api/hooks/account'
import {
  useAcceptGroupInvite,
  useCreateGroup,
  useGroups,
  useRemoveGroupMember,
} from '@/lib/api/hooks/social'
import { getErrorDetail } from '@f0rge/ui/api'
import { toast } from 'sonner'
import type { GroupListItem } from '@/lib/api/types/social'

export default function GroupsClient() {
  const account = useAccount()
  const groups = useGroups()
  const createGroup = useCreateGroup()
  const acceptInvite = useAcceptGroupInvite()
  const removeMember = useRemoveGroupMember()
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)

  const myHandle = account.data?.handle ?? ''

  const onCreate = async () => {
    const trimmed = name.trim()
    if (!trimmed) return
    setError(null)
    try {
      await createGroup.mutateAsync(trimmed)
      toast.success('Group created')
      setName('')
    } catch (err) {
      setError(getErrorDetail(err, 'Could not create group'))
    }
  }

  const onAccept = async (groupId: string) => {
    try {
      await acceptInvite.mutateAsync(groupId)
      toast.success('Joined group')
    } catch (err) {
      toast.error(getErrorDetail(err, 'Could not accept invite'))
    }
  }

  const onDecline = async (groupId: string) => {
    if (!myHandle) return
    try {
      await removeMember.mutateAsync({ id: groupId, handle: myHandle })
      toast.success('Invite declined')
    } catch (err) {
      toast.error(getErrorDetail(err, 'Could not decline invite'))
    }
  }

  const items = groups.data ?? []
  const invited = items.filter((g) => g.my_status === 'invited')
  const joined = items.filter((g) => g.my_status === 'joined')

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
            <UsersRound className="size-5 text-muted-foreground" />
            <h1 className="text-xl font-semibold tracking-tight">Groups</h1>
          </div>
        }
        subtitle="Organize connected people into named groups."
      />

      <Card className="space-y-3 p-4">
        <Label htmlFor="group-name">Create a group</Label>
        <div className="flex gap-2">
          <Input
            id="group-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="our family"
            maxLength={60}
            className="flex-1"
          />
          <Button
            type="button"
            onClick={onCreate}
            disabled={createGroup.isPending || name.trim().length === 0}
          >
            Create
          </Button>
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
      </Card>

      {groups.isError && (
        <FetchError message="Could not load groups." onRetry={() => groups.refetch()} />
      )}

      {invited.length > 0 && (
        <Section title="Invitations">
          {invited.map((group) => (
            <GroupRow
              key={group.id}
              group={group}
              actions={
                <>
                  <Button
                    size="sm"
                    onClick={() => onAccept(group.id)}
                    disabled={acceptInvite.isPending}
                  >
                    Accept
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onDecline(group.id)}
                    disabled={removeMember.isPending}
                  >
                    Decline
                  </Button>
                </>
              }
            />
          ))}
        </Section>
      )}

      <Section title="Your groups">
        {groups.isLoading && (
          <p className="text-sm text-muted-foreground">Loading groups...</p>
        )}
        {!groups.isLoading && joined.length === 0 && (
          <p className="text-sm text-muted-foreground">No groups yet.</p>
        )}
        {joined.map((group) => (
          <GroupRow key={group.id} group={group} href={`/people/groups/${group.id}`} />
        ))}
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

function GroupRow({
  group,
  href,
  actions,
}: {
  group: GroupListItem
  href?: string
  actions?: React.ReactNode
}) {
  const inner = (
    <div className="flex items-center gap-3 rounded-lg border border-muted px-3 py-2">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-medium">{group.name}</p>
          <StatusChip status={group.my_status} role={group.my_role} />
        </div>
        <p className="text-xs text-muted-foreground">
          {group.member_count} member{group.member_count === 1 ? '' : 's'} · @{group.owner.handle}
        </p>
      </div>
      {actions && <div className="flex shrink-0 gap-2">{actions}</div>}
    </div>
  )

  if (href) {
    return (
      <Link href={href} className="block transition-colors hover:opacity-80">
        {inner}
      </Link>
    )
  }

  return inner
}

function StatusChip({
  status,
  role,
}: {
  status: GroupListItem['my_status']
  role: GroupListItem['my_role']
}) {
  if (status === 'invited') {
    return (
      <Badge variant="secondary" className="text-[10px]">
        Invited
      </Badge>
    )
  }
  if (role === 'owner') {
    return (
      <Badge variant="outline" className="text-[10px]">
        Owner
      </Badge>
    )
  }
  return null
}
