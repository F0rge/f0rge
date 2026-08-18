'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import {
  ArrowLeft,
  Tag,
  UserPlus,
  Users,
  UsersRound,
} from 'lucide-react'
import { Button, Card, useDebouncedValue } from '@f0rge/ui'
import { TextInput, useForm } from '@f0rge/ui/forms'
import { HubRow } from '@/components/customize/hub-row'
import { PageHeader } from '@/components/layout/page-header'
import { PageShell } from '@/components/layout/page-shell'
import { useAccount, useHandleAvailable, useUpdateAccount } from '@/lib/api/hooks'
import { useConnections, useGroups, useMealTags } from '@/lib/api/hooks/social'
import { getErrorDetail } from '@f0rge/ui/api'
import { toast } from 'sonner'
import { statusText } from '@/lib/ui/status'

function ClaimHandleCard() {
  const account = useAccount()
  const updateAccount = useUpdateAccount()
  const [handleDraft, setHandleDraft] = useState('')
  const [error, setError] = useState<string | null>(null)

  const form = useForm({
    mode: 'uncontrolled',
    initialValues: { handle: '' },
    validate: {
      handle: (value) => {
        if (value.length < 3) return 'Handle must be at least 3 characters'
        if (!/^[a-z0-9_]+$/.test(value)) return 'Use 3–30 characters: a-z, 0-9, _'
        return null
      },
    },
    onValuesChange: (values) => setHandleDraft(values.handle),
  })

  const debounced = useDebouncedValue(handleDraft, 400)
  const availability = useHandleAvailable(debounced)

  const status = useMemo(() => {
    if (debounced.length < 3) return null
    if (availability.isLoading) return 'checking'
    if (availability.data?.available) return 'available'
    return 'taken'
  }, [availability.data?.available, availability.isLoading, debounced.length])

  const handleSave = form.onSubmit(async (values) => {
    setError(null)
    try {
      await updateAccount.mutateAsync({
        handle: values.handle.trim().toLowerCase().replace(/^@/, ''),
      })
      toast.success('Handle claimed')
    } catch (err) {
      setError(getErrorDetail(err, 'Could not claim handle'))
    }
  })

  if (!account.data || account.data.handle) return null

  return (
    <Card className="p-4">
      <h2 className="text-sm font-semibold">Claim your @handle</h2>
      <p className="mt-1 text-xs text-muted-foreground">
        People find you by handle. You can change it later in Account.
      </p>
      <form onSubmit={handleSave} className="mt-3 space-y-2">
        <TextInput
          key={form.key('handle')}
          label="Handle"
          leftSection={<span className="text-sm text-muted-foreground">@</span>}
          placeholder="your_name"
          autoComplete="off"
          spellCheck={false}
          {...form.getInputProps('handle')}
        />
        {status === 'available' && (
          <p className={`text-xs ${statusText.ok}`}>Available</p>
        )}
        {status === 'taken' && (
          <p className="text-xs text-destructive">Already taken</p>
        )}
        {error && <p className="text-xs text-destructive">{error}</p>}
        <Button
          type="submit"
          disabled={updateAccount.isPending || status !== 'available'}
          className="w-full sm:w-auto"
        >
          {updateAccount.isPending ? 'Saving...' : 'Claim handle'}
        </Button>
      </form>
    </Card>
  )
}

export default function PeopleClient() {
  const connections = useConnections()
  const groups = useGroups()
  const mealTags = useMealTags()
  const pendingIncoming = connections.data?.pending_incoming.length ?? 0
  const pendingGroupInvites = groups.data?.filter((g) => g.my_status === 'invited').length ?? 0
  const pendingMealTags = mealTags.data?.incoming_pending.length ?? 0

  const hubItems = [
    {
      href: '/people/connections',
      icon: <UserPlus className="size-4" />,
      title: pendingIncoming > 0 ? `Connections (${pendingIncoming} pending)` : 'Connections',
      description: 'Send requests and manage people you can tag on meals.',
    },
    {
      href: '/people/groups',
      icon: <UsersRound className="size-4" />,
      title:
        pendingGroupInvites > 0
          ? `Groups (${pendingGroupInvites} invite${pendingGroupInvites === 1 ? '' : 's'})`
          : 'Groups',
      description: 'Organize connected people into named groups.',
    },
    {
      href: '/people/tags',
      icon: <Tag className="size-4" />,
      title:
        pendingMealTags > 0
          ? `Tagged meals (${pendingMealTags} pending)`
          : 'Tagged meals',
      description: 'Review meal tags waiting for your approval.',
    },
  ]

  return (
    <PageShell>
      <PageHeader
        data-tour="people-hub"
        leading={
          <Link
            href="/checkin"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
            Back
          </Link>
        }
        title={
          <div className="flex items-center gap-2">
            <Users className="size-5 text-muted-foreground" />
            <h1 className="text-xl font-semibold tracking-tight">People</h1>
          </div>
        }
        subtitle="Connections, groups, and meal tags."
      />

      <div className="space-y-4">
        <ClaimHandleCard />

        <Card className="overflow-hidden py-0 lg:hidden">
          {hubItems.map((item) => (
            <HubRow key={item.href} {...item} />
          ))}
        </Card>

        <div className="hidden lg:grid lg:grid-cols-2 lg:gap-4">
          {hubItems.map((item) => (
            <Card key={item.href} className="overflow-hidden py-0">
              <HubRow {...item} variant="tile" />
            </Card>
          ))}
        </div>
      </div>
    </PageShell>
  )
}
