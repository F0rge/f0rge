'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import {
  ArrowLeft,
  Bell,
  Tag,
  UserPlus,
  Users,
  UsersRound,
} from 'lucide-react'
import { Button, Card, Input, Label } from '@f0rge/ui'
import { HubRow } from '@/components/customize/hub-row'
import { PageHeader } from '@/components/layout/page-header'
import { PageShell } from '@/components/layout/page-shell'
import { useAccount, useHandleAvailable, useUpdateAccount } from '@/lib/api/hooks'
import { getErrorDetail } from '@f0rge/ui/api'
import { toast } from 'sonner'

const HUB_ITEMS = [
  {
    href: '/people/connections',
    icon: <UserPlus className="size-4" />,
    title: 'Connections',
    description: 'Send requests and manage people you can tag on meals.',
    comingSoon: true,
  },
  {
    href: '/people/groups',
    icon: <UsersRound className="size-4" />,
    title: 'Groups',
    description: 'Organize connected people into named groups.',
    comingSoon: true,
  },
  {
    href: '/people/tags',
    icon: <Tag className="size-4" />,
    title: 'Tagged meals',
    description: 'Review meal tags waiting for your approval.',
    comingSoon: true,
  },
  {
    href: '/people/notifications',
    icon: <Bell className="size-4" />,
    title: 'Notifications',
    description: 'Connection requests, invites, and tag activity.',
    comingSoon: true,
  },
]

function ClaimHandleCard() {
  const account = useAccount()
  const updateAccount = useUpdateAccount()
  const [handle, setHandle] = useState('')
  const [error, setError] = useState<string | null>(null)
  const debounced = useDebouncedValue(handle, 400)
  const availability = useHandleAvailable(debounced)

  const status = useMemo(() => {
    if (debounced.length < 3) return null
    if (availability.isLoading) return 'checking'
    if (availability.data?.available) return 'available'
    return 'taken'
  }, [availability.data?.available, availability.isLoading, debounced.length])

  const handleSave = async () => {
    setError(null)
    try {
      await updateAccount.mutateAsync({ handle: handle.trim().toLowerCase().replace(/^@/, '') })
      toast.success('Handle claimed')
    } catch (err) {
      setError(getErrorDetail(err, 'Could not claim handle'))
    }
  }

  if (!account.data || account.data.handle) return null

  return (
    <Card className="p-4">
      <h2 className="text-sm font-semibold">Claim your @handle</h2>
      <p className="mt-1 text-xs text-muted-foreground">
        People find you by handle. You can change it later in Account.
      </p>
      <div className="mt-3 space-y-2">
        <Label htmlFor="claim-handle">Handle</Label>
        <div className="relative">
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
            @
          </span>
          <Input
            id="claim-handle"
            value={handle}
            onChange={(e) => setHandle(e.target.value.toLowerCase().replace(/^@/, ''))}
            className="pl-7"
            placeholder="your_name"
            autoComplete="off"
            spellCheck={false}
          />
        </div>
        {status === 'available' && (
          <p className="text-xs text-emerald-600">Available</p>
        )}
        {status === 'taken' && (
          <p className="text-xs text-destructive">Already taken</p>
        )}
        {error && <p className="text-xs text-destructive">{error}</p>}
        <Button
          type="button"
          onClick={handleSave}
          disabled={updateAccount.isPending || status !== 'available'}
          className="w-full sm:w-auto"
        >
          {updateAccount.isPending ? 'Saving...' : 'Claim handle'}
        </Button>
      </div>
    </Card>
  )
}

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs)
    return () => window.clearTimeout(timer)
  }, [value, delayMs])
  return debounced
}

export default function PeopleClient() {
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
        subtitle="Connections, groups, meal tags, and notifications."
      />

      <div className="space-y-4">
        <ClaimHandleCard />

        <Card className="overflow-hidden py-0 lg:hidden">
          {HUB_ITEMS.map((item) => (
            <HubRow key={item.href} {...item} />
          ))}
        </Card>

        <div className="hidden lg:grid lg:grid-cols-2 lg:gap-4">
          {HUB_ITEMS.map((item) => (
            <Card key={item.href} className="overflow-hidden py-0">
              <HubRow {...item} variant="tile" />
            </Card>
          ))}
        </div>
      </div>
    </PageShell>
  )
}
