import { Loader2 } from 'lucide-react'

export default function LabsLoading() {
  return (
    <div className="mx-auto w-full max-w-lg p-4">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold tracking-tight">Labs</h1>
      </div>
      <div className="flex items-center justify-center py-12">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    </div>
  )
}
