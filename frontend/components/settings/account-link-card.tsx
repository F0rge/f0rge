import Link from 'next/link'
import { UserRound } from 'lucide-react'
import { SettingsCard } from './settings-card'

export function AccountLinkCard() {
  return (
    <Link href="/account" className="block rounded-xl transition-opacity hover:opacity-90">
      <SettingsCard icon={UserRound} title="Account">
        <p className="text-sm text-muted-foreground">Profile, password, data export</p>
      </SettingsCard>
    </Link>
  )
}
