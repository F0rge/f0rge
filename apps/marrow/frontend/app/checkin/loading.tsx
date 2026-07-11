import { Loader2 } from 'lucide-react'

export default function CheckinLoading() {
  return (
    <div className="mx-auto w-full max-w-7xl p-4 lg:px-8">
      <div className="mb-6">
        <h1 className="text-xl font-semibold tracking-tight">Check-in</h1>
      </div>
      <div className="flex items-center justify-center py-12">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    </div>
  )
}
