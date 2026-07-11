'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { KeyRound } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { SettingsCard } from '@/components/settings/settings-card'
import { useChangePassword } from '@/lib/api/hooks'
import { handleMutationError } from '@/lib/api/client'

export function PasswordSection() {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const changePassword = useChangePassword()

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (newPassword !== confirmPassword) {
      toast.error('Passwords do not match')
      return
    }
    try {
      await changePassword.mutateAsync({
        current_password: currentPassword,
        new_password: newPassword,
      })
      toast.success('Password changed')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err) {
      handleMutationError(err, 'Failed to change password')
    }
  }

  return (
    <SettingsCard icon={KeyRound} title="Password">
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="current-password">Current password</Label>
          <Input
            id="current-password"
            type="password"
            autoComplete="current-password"
            required
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="new-password">New password</Label>
          <Input
            id="new-password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="confirm-password">Confirm new password</Label>
          <Input
            id="confirm-password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
          />
        </div>

        <Button type="submit" disabled={changePassword.isPending} className="w-full sm:w-auto">
          {changePassword.isPending ? 'Saving...' : 'Change password'}
        </Button>
      </form>
    </SettingsCard>
  )
}
