'use client'

import { Loader2 } from 'lucide-react'
import { FetchError } from '@f0rge/ui'
import { handleMutationError } from '@f0rge/ui/api'
import { PageHeader } from '@/components/layout/page-header'
import { PageShell } from '@/components/layout/page-shell'
import { HypothesisCard } from '@/components/hypotheses/hypothesis-card'
import { NOf1Card } from '@/components/hypotheses/n-of-1-card'
import { EmptyMark } from '@/components/shared/color-artifact'
import { useHypotheses, useUpdateHypothesis } from '@/lib/api/hooks'
import type { Hypothesis, HypothesisStatus } from '@/lib/api/types'

const SECTIONS: { status: HypothesisStatus; title: string }[] = [
  { status: 'live', title: 'Live' },
  { status: 'weakening', title: 'Weakening' },
  { status: 'parked', title: 'Parked' },
  { status: 'killed', title: 'Killed' },
]

export default function HypothesesPage() {
  const { data: rows, isLoading, isError, refetch } = useHypotheses()
  const update = useUpdateHypothesis()

  async function onStatusChange(row: Hypothesis, status: HypothesisStatus) {
    try {
      await update.mutateAsync({ id: row.id, data: { status } })
    } catch (err) {
      handleMutationError(err, 'Could not update status.')
    }
  }

  return (
    <PageShell>
      <PageHeader
        title="Hypothesis scoreboard"
        subtitle="Tracked questions and kill-tests. This is a log, not a diagnosis."
      />
      <div className="space-y-6">
        <NOf1Card />
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="size-6 animate-spin text-muted-foreground" />
          </div>
        ) : isError ? (
          <FetchError message="Failed to load the scoreboard." onRetry={() => refetch()} />
        ) : !rows || rows.length === 0 ? (
          <div className="flex flex-col items-center py-12 text-center">
            <EmptyMark className="mb-3" />
            <h2 className="mb-1 text-lg font-semibold">No hypotheses yet</h2>
            <p className="max-w-sm text-sm text-muted-foreground">
              Add rows through the API or MCP. Killed questions stay on the board.
            </p>
          </div>
        ) : (
          SECTIONS.map((section) => {
            const items = rows.filter((row) => row.status === section.status)
            if (items.length === 0) return null
            return (
              <section key={section.status} className="space-y-2">
                <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {section.title}
                </h2>
                {items.map((row) => (
                  <HypothesisCard
                    key={row.id}
                    hypothesis={row}
                    onStatusChange={(status) => void onStatusChange(row, status)}
                  />
                ))}
              </section>
            )
          })
        )}
      </div>
    </PageShell>
  )
}
