'use client'

import dynamic from 'next/dynamic'
import { PageShell } from '@/components/layout/page-shell'

const DefaultsClient = dynamic(() => import('./defaults-client'), {
  ssr: false,
  loading: () => (
    <PageShell>
      <div className="h-6 w-32 animate-pulse rounded bg-muted" />
      <div className="mt-4 h-7 w-48 animate-pulse rounded bg-muted" />
      <div className="mt-3 h-14 w-full animate-pulse rounded bg-muted" />
      <div className="mt-6 h-5 w-28 animate-pulse rounded bg-muted" />
      <div className="mt-2 grid grid-cols-3 gap-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-12 animate-pulse rounded-xl bg-muted" />
        ))}
      </div>
    </PageShell>
  ),
})

export default function DefaultsPage() {
  return <DefaultsClient />
}
