'use client'

import Link from 'next/link'
import { ArrowLeft, Tag } from 'lucide-react'
import { Button, Card } from '@f0rge/ui'
import { formatDisplayDate } from '@f0rge/ui'
import { cn } from '@f0rge/ui'
import { PeerAvatar } from '@/components/people/peer-avatar'
import { PageHeader } from '@/components/layout/page-header'
import { PageShell } from '@/components/layout/page-shell'
import {
  useApproveMealTag,
  useCancelMealTag,
  useDeclineMealTag,
  useMealTags,
} from '@/lib/api/hooks/social'
import type { IncomingMealTag, MealTagStatus, OutgoingMealTag } from '@/lib/api/types/social'
import { toast } from 'sonner'
import { getErrorDetail } from '@f0rge/ui/api'

const STATUS_LABELS: Record<MealTagStatus, string> = {
  pending_analysis: 'Pending analysis',
  pending_approval: 'Awaiting approval',
  delivered: 'Delivered',
  declined: 'Declined',
  cancelled: 'Cancelled',
}

const STATUS_CLASS: Record<MealTagStatus, string> = {
  pending_analysis: 'bg-amber-100 text-amber-800',
  pending_approval: 'bg-sky-100 text-sky-800',
  delivered: 'bg-emerald-100 text-emerald-800',
  declined: 'bg-muted text-muted-foreground',
  cancelled: 'bg-muted text-muted-foreground',
}

function mealTitle(tag: { source_dish_name: string | null; source_label: string | null }) {
  return tag.source_dish_name?.trim() || tag.source_label?.trim() || 'Untitled meal'
}

function IncomingCard({ tag }: { tag: IncomingMealTag }) {
  const approve = useApproveMealTag()
  const decline = useDeclineMealTag()
  const busy = approve.isPending || decline.isPending

  const run = async (action: 'approve' | 'decline') => {
    try {
      if (action === 'approve') {
        await approve.mutateAsync(tag.id)
        toast.success('Meal added to your timeline')
      } else {
        await decline.mutateAsync(tag.id)
        toast.success('Tag declined')
      }
    } catch (err) {
      toast.error(getErrorDetail(err, action === 'approve' ? 'Could not approve' : 'Could not decline'))
    }
  }

  return (
    <div className="space-y-3 rounded-lg border border-border p-4">
      <div className="flex items-start gap-3">
        <PeerAvatar
          handle={tag.tagger.handle}
          avatarDefaultIndex={tag.tagger.avatar_default_index}
          hasCustomAvatar={tag.tagger.has_custom_avatar}
        />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">@{tag.tagger.handle}</p>
          {tag.tagger.display_name && (
            <p className="text-xs text-muted-foreground">{tag.tagger.display_name}</p>
          )}
        </div>
      </div>
      <div>
        <p className="text-sm font-semibold">{mealTitle(tag)}</p>
        {tag.source_label && tag.source_dish_name && (
          <p className="text-xs text-muted-foreground">{tag.source_label}</p>
        )}
        <p className="mt-1 text-xs text-muted-foreground">
          Meal date: {formatDisplayDate(tag.source_date)}
        </p>
      </div>
      <div className="flex gap-2">
        <Button type="button" size="sm" onClick={() => void run('approve')} disabled={busy}>
          Approve
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => void run('decline')}
          disabled={busy}
        >
          Decline
        </Button>
      </div>
    </div>
  )
}

function OutgoingRow({ tag }: { tag: OutgoingMealTag }) {
  const cancel = useCancelMealTag()
  const canCancel = tag.status === 'pending_analysis' || tag.status === 'pending_approval'

  const onCancel = async () => {
    try {
      await cancel.mutateAsync(tag.id)
      toast.success('Tag cancelled')
    } catch (err) {
      toast.error(getErrorDetail(err, 'Could not cancel tag'))
    }
  }

  return (
    <div className="border-t border-muted px-4 py-3.5 first:border-t-0">
      <div className="flex items-start gap-3">
        <PeerAvatar
          handle={tag.tagged_user.handle}
          avatarDefaultIndex={tag.tagged_user.avatar_default_index}
          hasCustomAvatar={tag.tagged_user.has_custom_avatar}
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-medium">@{tag.tagged_user.handle}</p>
            <span
              className={cn(
                'rounded-full px-2 py-0.5 text-[10px] font-medium',
                STATUS_CLASS[tag.status],
              )}
            >
              {STATUS_LABELS[tag.status]}
            </span>
          </div>
          <p className="mt-1 text-sm">{mealTitle(tag)}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {formatDisplayDate(tag.source_date)}
            {tag.status === 'pending_analysis' && (
              <> · Delivers after you confirm the meal&apos;s analysis</>
            )}
          </p>
        </div>
        {canCancel && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => void onCancel()}
            disabled={cancel.isPending}
          >
            Cancel
          </Button>
        )}
      </div>
    </div>
  )
}

export default function TagsClient() {
  const mealTags = useMealTags()
  const incoming = mealTags.data?.incoming_pending ?? []
  const outgoing = mealTags.data?.outgoing ?? []

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
            <Tag className="size-5 text-muted-foreground" />
            <h1 className="text-xl font-semibold tracking-tight">Tagged meals</h1>
          </div>
        }
        subtitle="Approve incoming tags and track meals you shared."
      />

      <div className="space-y-6">
        <section className="space-y-3">
          <h2 className="text-sm font-semibold">Waiting for your approval</h2>
          {mealTags.isLoading && (
            <p className="text-sm text-muted-foreground">Loading...</p>
          )}
          {!mealTags.isLoading && incoming.length === 0 && (
            <p className="text-sm text-muted-foreground">No tags waiting for approval.</p>
          )}
          {incoming.map((tag) => (
            <IncomingCard key={tag.id} tag={tag} />
          ))}
        </section>

        <section className="space-y-3">
          <h2 className="text-sm font-semibold">Meals you tagged</h2>
          <Card className="overflow-hidden py-0">
            {mealTags.isLoading && (
              <p className="px-4 py-6 text-sm text-muted-foreground">Loading...</p>
            )}
            {!mealTags.isLoading && outgoing.length === 0 && (
              <p className="px-4 py-6 text-sm text-muted-foreground">No outgoing tags yet.</p>
            )}
            {outgoing.map((tag) => (
              <OutgoingRow key={tag.id} tag={tag} />
            ))}
          </Card>
        </section>
      </div>
    </PageShell>
  )
}
