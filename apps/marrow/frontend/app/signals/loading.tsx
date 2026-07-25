import { Loader2 } from 'lucide-react'
import { PageShell } from '@/components/layout/page-shell'

export default function SignalsLoading() {
  return (
    <PageShell>
      <div className="mx-auto w-full max-w-lg">
        <div className="mb-4">
          <h1 className="text-xl font-semibold tracking-tight">Signals</h1>
          <p className="text-sm text-muted-foreground">What moves your outcomes</p>
        </div>
        <div className="flex items-center justify-center py-12">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      </div>
    </PageShell>
  )
}
