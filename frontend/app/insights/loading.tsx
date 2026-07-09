import { Loader2 } from 'lucide-react'
import { PageShell } from '@/components/layout/page-shell'

export default function InsightsLoading() {
  return (
    <PageShell>
      <div className="mb-4">
        <h1 className="text-xl font-semibold tracking-tight">Insights</h1>
        <p className="text-sm text-muted-foreground">Analytics &amp; correlations</p>
      </div>
      <div className="flex items-center justify-center py-12">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    </PageShell>
  )
}
