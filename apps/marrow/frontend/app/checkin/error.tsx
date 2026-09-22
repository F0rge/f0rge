'use client'

import { FetchError } from '@f0rge/ui'
import { CheckinPageHeader } from '@/components/checkin/checkin-page-header'
import { PageShell } from '@/components/layout/page-shell'
import { formatLocalDate } from '@f0rge/ui'

export default function CheckinError({
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  const today = formatLocalDate(new Date())

  return (
    <PageShell>
      <CheckinPageHeader date={today} />
      <FetchError message="Failed to load check-in." onRetry={reset} />
    </PageShell>
  )
}
