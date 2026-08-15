'use client'

import { toast } from 'sonner'
import { KeyRound } from 'lucide-react'
import { Button } from '@f0rge/ui'
import { PasswordInput, useForm } from '@f0rge/ui/forms'
import { SettingsCard } from '@/components/settings/settings-card'
import { useChangePassword } from '@/lib/api/hooks'
import { handleMutationError } from '@f0rge/ui/api'

export function PasswordSection() {
  const changePassword = useChangePassword()

  const form = useForm({
    mode: 'uncontrolled',
    initialValues: {
      currentPassword: '',
      newPassword: '',
      confirmPassword: '',
    },
    validate: {
      currentPassword: (value) => (value ? null : 'Current password is required'),
      newPassword: (value) => (value.length >= 8 ? null : 'Password must be at least 8 characters'),
      confirmPassword: (value, values) =>
        value === values.newPassword ? null : 'Passwords do not match',
    },
  })

  const handleSubmit = form.onSubmit(async (values) => {
    try {
      await changePassword.mutateAsync({
        current_password: values.currentPassword,
        new_password: values.newPassword,
      })
      toast.success('Password changed')
      form.reset()
    } catch (err) {
      handleMutationError(err, 'Failed to change password')
    }
  })

  return (
    <SettingsCard icon={KeyRound} title="Password">
      <form onSubmit={handleSubmit} className="space-y-3">
        <PasswordInput
          key={form.key('currentPassword')}
          label="Current password"
          autoComplete="current-password"
          required
          {...form.getInputProps('currentPassword')}
        />

        <PasswordInput
          key={form.key('newPassword')}
          label="New password"
          autoComplete="new-password"
          required
          {...form.getInputProps('newPassword')}
        />

        <PasswordInput
          key={form.key('confirmPassword')}
          label="Confirm new password"
          autoComplete="new-password"
          required
          {...form.getInputProps('confirmPassword')}
        />

        <Button type="submit" disabled={changePassword.isPending} className="w-full sm:w-auto">
          {changePassword.isPending ? 'Saving...' : 'Change password'}
        </Button>
      </form>
    </SettingsCard>
  )
}
