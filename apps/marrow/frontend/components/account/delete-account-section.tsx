'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQueryClient } from '@tanstack/react-query'
import { ShieldAlert } from 'lucide-react'
import { Button } from '@f0rge/ui'
import { Input } from '@f0rge/ui'
import { Label } from '@f0rge/ui'
import { SettingsCard } from '@/components/settings/settings-card'
import { useDeleteAccount } from '@/lib/api/hooks'
import { handleMutationError } from '@f0rge/ui/api'

export function DeleteAccountSection() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const [password, setPassword] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const deleteAccount = useDeleteAccount()

  const handleDelete = async () => {
    if (!confirmDelete) {
      setConfirmDelete(true)
      return
    }
    try {
      await deleteAccount.mutateAsync({ password })
      queryClient.clear()
      router.replace('/login')
    } catch (err) {
      handleMutationError(err, 'Failed to delete account')
    }
  }

  return (
    <SettingsCard icon={ShieldAlert} iconClassName="text-destructive" title="Delete account">
      <p className="text-sm text-muted-foreground">
        Permanently deletes your account and all data. This cannot be undone.
      </p>

      <div className="space-y-1.5">
        <Label htmlFor="delete-password">Password</Label>
        <Input
          id="delete-password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => {
            setPassword(e.target.value)
            setConfirmDelete(false)
          }}
        />
      </div>

      <Button
        type="button"
        variant="destructive"
        onClick={handleDelete}
        disabled={!password || deleteAccount.isPending}
        className="w-full sm:w-auto"
      >
        {deleteAccount.isPending
          ? 'Deleting...'
          : confirmDelete
            ? 'Confirm delete'
            : 'Delete my account'}
      </Button>
    </SettingsCard>
  )
}
