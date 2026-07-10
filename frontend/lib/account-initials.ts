import type { Account } from '@/lib/api/types'

export function getAccountInitials(account: Pick<Account, 'display_name' | 'email'>): string {
  const name = account.display_name?.trim()
  if (name) {
    const parts = name.split(/\s+/).filter(Boolean)
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    }
    return name.slice(0, 2).toUpperCase()
  }
  const local = account.email.split('@')[0] ?? ''
  return local.slice(0, 2).toUpperCase()
}
