'use client'

/**
 * /customize/reorder — page wrapper.
 *
 * The reorder UI reads per-user localStorage end-to-end, so there is nothing
 * meaningful for the server to render. Loading via next/dynamic({ ssr: false })
 * keeps the client-only code in `reorder-client.tsx` out of any SSR pass and
 * removes hydration-drift risk entirely.
 */

import dynamic from 'next/dynamic'
import { PageShell } from '@/components/layout/page-shell'

const ReorderClient = dynamic(() => import('./reorder-client'), {
  ssr: false,
  loading: () => (
    <PageShell>
      <div className="h-6 w-32 animate-pulse rounded bg-muted" />
      <div className="mt-4 h-7 w-56 animate-pulse rounded bg-muted" />
      <div className="mt-3 h-14 w-full animate-pulse rounded bg-muted" />
      <div className="mt-4 flex flex-col gap-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-16 w-full animate-pulse rounded-lg bg-muted" />
        ))}
      </div>
    </PageShell>
  ),
})

export default function ReorderPage() {
  return <ReorderClient />
}
