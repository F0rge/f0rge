'use client'

import { usePathname } from 'next/navigation'
import { ProfileMenu } from '@/components/layout/profile-menu'

/** In-flow chrome aligned to the same max-w-7xl column as PageShell. */
export function AppChrome() {
  const pathname = usePathname()

  if (pathname.startsWith('/login') || pathname.startsWith('/signup')) return null

  return (
    <div className="mx-auto flex w-full max-w-7xl justify-end px-4 pb-2 pt-[calc(16px+env(safe-area-inset-top))] lg:px-8">
      <ProfileMenu />
    </div>
  )
}
