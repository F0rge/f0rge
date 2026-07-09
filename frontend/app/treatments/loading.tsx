import { Loader2 } from 'lucide-react'
import { PageShell } from '@/components/layout/page-shell'

export default function TreatmentsLoading() {
  return (
    <PageShell>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold tracking-tight">Treatments</h1>
      </div>
      <div className="flex items-center justify-center py-12">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    </PageShell>
  )
}
