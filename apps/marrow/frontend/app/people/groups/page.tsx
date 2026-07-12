'use client'

import dynamic from 'next/dynamic'
import { PageShell } from '@/components/layout/page-shell'

const GroupsClient = dynamic(() => import('./groups-client'), {
  ssr: false,
  loading: () => (
    <PageShell>
      <div className="h-6 w-32 animate-pulse rounded bg-muted" />
      <div className="mt-4 h-40 w-full animate-pulse rounded bg-muted" />
    </PageShell>
  ),
})

export default function GroupsPage() {
  return <GroupsClient />
}
