import { Loader2 } from 'lucide-react'

export default function InsightsLoading() {
  return (
    <div className="mx-auto w-full max-w-lg p-4">
      <div className="mb-4">
        <h1 className="text-xl font-semibold tracking-tight">Insights</h1>
        <p className="text-sm text-muted-foreground">Analytics &amp; correlations</p>
      </div>
      <div className="flex items-center justify-center py-12">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    </div>
  )
}
