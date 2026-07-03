import { Loader2 } from 'lucide-react'

export default function HistoryDateLoading() {
  return (
    <div className="mx-auto w-full max-w-lg p-4">
      <div className="mb-6">
        <h1 className="text-xl font-semibold tracking-tight">History</h1>
      </div>
      <div className="flex items-center justify-center py-12">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    </div>
  )
}
