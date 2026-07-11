'use client'

/**
 * /customize/trackers — page wrapper.
 *
 * The trackers UI hits the API (tracker catalog) which is client-only in this
 * app. Loading via next/dynamic({ ssr: false }) keeps the client-only code in
 * `trackers-client.tsx` out of any SSR pass, mirroring the reorder page pattern.
 */

import dynamic from 'next/dynamic'
import { PageShell } from '@/components/layout/page-shell'

const TrackersClient = dynamic(() => import('./trackers-client'), {
  ssr: false,
  loading: () => (
    <PageShell>
      <div className="h-6 w-32 animate-pulse rounded bg-muted" />
      <div className="mt-4 h-7 w-48 animate-pulse rounded bg-muted" />
      <div className="mt-3 h-14 w-full animate-pulse rounded bg-muted" />
      <div className="mt-4 flex flex-col gap-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-14 w-full animate-pulse rounded-lg bg-muted" />
        ))}
      </div>
    </PageShell>
  ),
})

export default function TrackersPage() {
  return <TrackersClient />
}
