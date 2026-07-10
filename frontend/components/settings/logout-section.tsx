'use client'

import { useRouter } from 'next/navigation'
import { LogOut } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { SettingsCard } from '@/components/settings/settings-card'
import { useLogout } from '@/lib/api/hooks'
import { handleMutationError } from '@/lib/api/client'

export function LogoutSection() {
  const router = useRouter()
  const logout = useLogout()

  const handleLogout = async () => {
    try {
      await logout.mutateAsync()
      router.replace('/login')
    } catch (err) {
      handleMutationError(err, 'Could not log out')
    }
  }

  return (
    <SettingsCard title="Account">
      <p className="text-sm text-muted-foreground">End your session on this device.</p>
      <Button
        type="button"
        variant="outline"
        onClick={handleLogout}
        disabled={logout.isPending}
        className="w-full sm:w-auto"
      >
        <LogOut className="size-4" />
        Log out
      </Button>
    </SettingsCard>
  )
}
