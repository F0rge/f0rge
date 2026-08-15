'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQueryClient } from '@tanstack/react-query'
import { ShieldAlert } from 'lucide-react'
import { Button } from '@f0rge/ui'
import { PasswordInput, useForm } from '@f0rge/ui/forms'
import { SettingsCard } from '@/components/settings/settings-card'
import { useDeleteAccount } from '@/lib/api/hooks'
import { handleMutationError } from '@f0rge/ui/api'

export function DeleteAccountSection() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const deleteAccount = useDeleteAccount()

  const form = useForm({
    mode: 'uncontrolled',
    initialValues: { password: '' },
    validate: {
      password: (value) => (value ? null : 'Password is required'),
    },
    onValuesChange: () => setConfirmDelete(false),
  })

  const handleDelete = async () => {
    if (!confirmDelete) {
      setConfirmDelete(true)
      return
    }
    const { password } = form.getValues()
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

      <PasswordInput
        key={form.key('password')}
        label="Password"
        autoComplete="current-password"
        {...form.getInputProps('password')}
      />

      <Button
        type="button"
        variant="destructive"
        onClick={handleDelete}
        disabled={!form.getValues().password || deleteAccount.isPending}
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
