'use client'

import { FetchError } from '@f0rge/ui'
import { PageShell } from '@/components/layout/page-shell'
import { PageHeader } from '@/components/layout/page-header'

export default function HistoryError({
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <PageShell>
      <PageHeader title="History" />
      <FetchError message="Failed to load history." onRetry={reset} />
    </PageShell>
  )
}
