'use client'

import { ProfileMenu } from '@/components/layout/profile-menu'

/** Fixed chrome aligned to the same max-w-7xl column as PageShell. */
export function AppChrome() {
  return (
    <div className="pointer-events-none fixed top-[calc(16px+env(safe-area-inset-top))] right-0 left-0 z-50">
      <div className="mx-auto flex w-full max-w-7xl justify-end px-4 lg:px-8">
        <div className="pointer-events-auto">
          <ProfileMenu />
        </div>
      </div>
    </div>
  )
}
