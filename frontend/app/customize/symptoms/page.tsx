'use client'

/**
 * /customize/symptoms — page wrapper.
 *
 * The symptoms UI hits the API (symptom catalog) which is client-only in this
 * app. Loading via next/dynamic({ ssr: false }) keeps the client-only code in
 * `symptoms-client.tsx` out of any SSR pass, mirroring the trackers page pattern.
 */

import dynamic from 'next/dynamic'
import { PageShell } from '@/components/layout/page-shell'

const SymptomsClient = dynamic(() => import('./symptoms-client'), {
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

export default function SymptomsPage() {
  return <SymptomsClient />
}
