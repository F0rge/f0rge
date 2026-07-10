'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { UserRound } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { SettingsCard } from '@/components/settings/settings-card'
import { useAccount, useUpdateAccount } from '@/lib/api/hooks'
import { handleMutationError } from '@/lib/api/client'
import type { Account } from '@/lib/api/types'

export function ProfileSection() {
  const account = useAccount()

  if (!account.data) {
    return (
      <SettingsCard icon={UserRound} title="Profile">
        <p className="text-sm text-muted-foreground">
          {account.isLoading ? 'Loading...' : 'Could not load account'}
        </p>
      </SettingsCard>
    )
  }

  return <ProfileForm account={account.data} />
}

function ProfileForm({ account }: { account: Account }) {
  const [displayName, setDisplayName] = useState(account.display_name ?? '')
  const updateAccount = useUpdateAccount()

  const handleSave = async () => {
    try {
      await updateAccount.mutateAsync({ display_name: displayName.trim() || null })
      toast.success('Profile updated')
    } catch (err) {
      handleMutationError(err, 'Failed to update profile')
    }
  }

  return (
    <SettingsCard icon={UserRound} title="Profile">
      <div className="space-y-1.5">
        <Label>Email</Label>
        <p className="text-sm text-muted-foreground">{account.email}</p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="display-name">Display name</Label>
        <Input
          id="display-name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="Optional"
        />
      </div>

      <Button
        type="button"
        onClick={handleSave}
        disabled={updateAccount.isPending}
        className="w-full sm:w-auto"
      >
        {updateAccount.isPending ? 'Saving...' : 'Save'}
      </Button>
    </SettingsCard>
  )
}
