'use client'

import { FetchError } from '@f0rge/ui'
import { PageShell } from '@/components/layout/page-shell'

export default function SignalsError({
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <PageShell>
      <div className="mx-auto w-full max-w-lg">
        <div className="mb-4">
          <h1 className="text-xl font-semibold tracking-tight">Signals</h1>
          <p className="text-sm text-muted-foreground">What moves your outcomes</p>
        </div>
        <FetchError message="Failed to load signals." onRetry={reset} />
      </div>
    </PageShell>
  )
}
