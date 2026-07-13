'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { ArrowLeft, UsersRound } from 'lucide-react'
import { Badge, Button, Card, Input, Label } from '@f0rge/ui'
import { FetchError } from '@f0rge/ui'
import { ConfirmActionDialog } from '@/components/people/confirm-action-dialog'
import { PeerAvatar } from '@/components/people/peer-avatar'
import { PageHeader } from '@/components/layout/page-header'
import { PageShell } from '@/components/layout/page-shell'
import { useAccount } from '@/lib/api/hooks/account'
import {
  useAcceptGroupInvite,
  useConnections,
  useDeleteGroup,
  useGroup,
  useInviteToGroup,
  useRemoveGroupMember,
  useRenameGroup,
  useUserLookup,
} from '@/lib/api/hooks/social'
import { getErrorDetail } from '@f0rge/ui/api'
import { toast } from 'sonner'
import type { GroupMember } from '@/lib/api/types/social'

type ConfirmAction = 'leave' | 'delete' | 'remove'

export default function GroupDetailClient() {
  const params = useParams<{ id: string }>()
  const router = useRouter()
  const groupId = params.id
  const account = useAccount()
  const group = useGroup(groupId)
  const connections = useConnections()
  const renameGroup = useRenameGroup()
  const deleteGroup = useDeleteGroup()
  const inviteToGroup = useInviteToGroup()
  const acceptInvite = useAcceptGroupInvite()
  const removeMember = useRemoveGroupMember()

  const [name, setName] = useState('')
  const [nameDirty, setNameDirty] = useState(false)
  const [inviteHandle, setInviteHandle] = useState('')
  const [inviteError, setInviteError] = useState<string | null>(null)
  const [confirm, setConfirm] = useState<{ action: ConfirmAction; handle?: string } | null>(null)

  const myHandle = account.data?.handle ?? ''
  const data = group.data
  const isOwner = data?.my_role === 'owner'
  const isInvited = data?.my_status === 'invited'

  const acceptedHandles = useMemo(
    () => new Set(connections.data?.accepted.map((c) => c.user.handle) ?? []),
    [connections.data?.accepted],
  )
  const lookup = useUserLookup(inviteHandle)
  const connectedPreview =
    lookup.data && acceptedHandles.has(lookup.data.handle) ? lookup.data : null

  const displayName = nameDirty ? name : (data?.name ?? '')

  const onRename = async () => {
    const trimmed = name.trim()
    if (!trimmed || !data) return
    try {
      await renameGroup.mutateAsync({ id: data.id, name: trimmed })
      toast.success('Group renamed')
      setNameDirty(false)
    } catch (err) {
      toast.error(getErrorDetail(err, 'Could not rename group'))
    }
  }

  const onInvite = async () => {
    if (!data) return
    setInviteError(null)
    const handle = inviteHandle.trim().toLowerCase().replace(/^@/, '')
    if (!acceptedHandles.has(handle)) {
      setInviteError('You can only invite connected people')
      return
    }
    try {
      await inviteToGroup.mutateAsync({ id: data.id, handle })
      toast.success('Invite sent')
      setInviteHandle('')
    } catch (err) {
      setInviteError(getErrorDetail(err, 'Could not send invite'))
    }
  }

  const runConfirm = async () => {
    if (!data || !confirm) return
    try {
      if (confirm.action === 'delete') {
        await deleteGroup.mutateAsync(data.id)
        toast.success('Group deleted')
        router.push('/people/groups')
        return
      }
      const handle = confirm.handle ?? myHandle
      await removeMember.mutateAsync({ id: data.id, handle })
      if (confirm.action === 'leave') {
        toast.success('Left group')
        router.push('/people/groups')
      } else {
        toast.success('Member removed')
      }
      setConfirm(null)
    } catch (err) {
      toast.error(getErrorDetail(err, 'Action failed'))
    }
  }

  const confirmCopy = (() => {
    if (!confirm || !data) return null
    if (confirm.action === 'delete') {
      return {
        title: 'Delete group?',
        description: `"${data.name}" and all members will be removed. This cannot be undone.`,
        confirmLabel: 'Delete group',
        destructive: true,
      }
    }
    if (confirm.action === 'leave') {
      return {
        title: 'Leave group?',
        description: `You will leave "${data.name}".`,
        confirmLabel: 'Leave group',
        destructive: true,
      }
    }
    return {
      title: 'Remove member?',
      description: `@${confirm.handle} will be removed from "${data.name}".`,
      confirmLabel: 'Remove',
      destructive: true,
    }
  })()

  return (
    <PageShell>
      <PageHeader
        leading={
          <Link
            href="/people/groups"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
            Back
          </Link>
        }
        title={
          <div className="flex items-center gap-2">
            <UsersRound className="size-5 text-muted-foreground" />
            <h1 className="text-xl font-semibold tracking-tight">{data?.name ?? 'Group'}</h1>
          </div>
        }
        subtitle={data ? `${data.members.filter((m) => m.status === 'joined').length} members` : undefined}
      />

      {group.isError && (
        <FetchError message="Could not load group." onRetry={() => group.refetch()} />
      )}

      {data && isInvited && (
        <Card className="mb-4 flex flex-wrap items-center gap-2 p-4">
          <p className="flex-1 text-sm">You have been invited to this group.</p>
          <Button
            size="sm"
            onClick={async () => {
              try {
                await acceptInvite.mutateAsync(data.id)
                toast.success('Joined group')
              } catch (err) {
                toast.error(getErrorDetail(err, 'Could not accept invite'))
              }
            }}
            disabled={acceptInvite.isPending}
          >
            Accept
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => removeMember.mutate({ id: data.id, handle: myHandle })}
            disabled={removeMember.isPending || !myHandle}
          >
            Decline
          </Button>
        </Card>
      )}

      {data && isOwner && (
        <Card className="mb-4 space-y-3 p-4">
          <Label htmlFor="rename-group">Group name</Label>
          <div className="flex gap-2">
            <Input
              id="rename-group"
              value={displayName}
              onChange={(e) => {
                setName(e.target.value)
                setNameDirty(true)
              }}
              maxLength={60}
              className="flex-1"
            />
            <Button
              type="button"
              onClick={onRename}
              disabled={renameGroup.isPending || !nameDirty || name.trim().length === 0}
            >
              Save
            </Button>
          </div>
        </Card>
      )}

      {data && data.my_status === 'joined' && (
        <Card className="mb-4 space-y-3 p-4">
          <Label htmlFor="invite-handle">Invite a connection</Label>
          <div className="flex gap-2">
            <Input
              id="invite-handle"
              value={inviteHandle}
              onChange={(e) => setInviteHandle(e.target.value.toLowerCase().replace(/^@/, ''))}
              placeholder="their_handle"
              className="flex-1"
            />
            <Button
              type="button"
              onClick={onInvite}
              disabled={inviteToGroup.isPending || inviteHandle.length < 3}
            >
              Invite
            </Button>
          </div>
          {connectedPreview && (
            <div className="flex items-center gap-3 rounded-lg border border-muted px-3 py-2">
              <PeerAvatar avatarDefaultIndex={connectedPreview.avatar_default_index} />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">@{connectedPreview.handle}</p>
                {connectedPreview.display_name && (
                  <p className="text-xs text-muted-foreground">{connectedPreview.display_name}</p>
                )}
              </div>
            </div>
          )}
          {inviteHandle.length >= 3 && lookup.data && !connectedPreview && (
            <p className="text-xs text-muted-foreground">Only connected people can be invited.</p>
          )}
          {inviteError && <p className="text-sm text-destructive">{inviteError}</p>}
        </Card>
      )}

      <section className="space-y-3">
        <h2 className="text-sm font-semibold">Members</h2>
        <Card className="space-y-2 p-3">
          {group.isLoading && <p className="text-sm text-muted-foreground">Loading members...</p>}
          {data?.members.map((member) => (
            <MemberRow
              key={member.handle}
              member={member}
              canRemove={isOwner && member.handle !== myHandle}
              onRemove={() => setConfirm({ action: 'remove', handle: member.handle })}
            />
          ))}
        </Card>
      </section>

      {data && data.my_status === 'joined' && !isOwner && (
        <div className="mt-6">
          <Button
            type="button"
            variant="outline"
            className="text-destructive hover:text-destructive"
            onClick={() => setConfirm({ action: 'leave' })}
          >
            Leave group
          </Button>
        </div>
      )}

      {data && isOwner && (
        <div className="mt-6">
          <Button
            type="button"
            variant="destructive"
            onClick={() => setConfirm({ action: 'delete' })}
          >
            Delete group
          </Button>
        </div>
      )}

      {confirmCopy && (
        <ConfirmActionDialog
          open={confirm !== null}
          onOpenChange={(open) => {
            if (!open) setConfirm(null)
          }}
          title={confirmCopy.title}
          description={confirmCopy.description}
          confirmLabel={confirmCopy.confirmLabel}
          destructive={confirmCopy.destructive}
          pending={deleteGroup.isPending || removeMember.isPending}
          onConfirm={runConfirm}
        />
      )}
    </PageShell>
  )
}

function MemberRow({
  member,
  canRemove,
  onRemove,
}: {
  member: GroupMember
  canRemove: boolean
  onRemove: () => void
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-muted px-3 py-2">
      <PeerAvatar avatarDefaultIndex={member.avatar_default_index} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-medium">@{member.handle}</p>
          {member.role === 'owner' && (
            <Badge variant="outline" className="text-[10px]">
              Owner
            </Badge>
          )}
          {member.status === 'invited' && (
            <Badge variant="secondary" className="text-[10px]">
              Pending
            </Badge>
          )}
        </div>
        {member.display_name && (
          <p className="text-xs text-muted-foreground">{member.display_name}</p>
        )}
      </div>
      {canRemove && (
        <Button type="button" size="sm" variant="outline" onClick={onRemove}>
          Remove
        </Button>
      )}
    </div>
  )
}
