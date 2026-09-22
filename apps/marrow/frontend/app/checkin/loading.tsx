import { CheckinBoardSkeleton } from '@/components/checkin/checkin-board-skeleton'

export default function CheckinLoading() {
  return (
    <div className="mx-auto w-full max-w-7xl px-4 pb-4 pt-[calc(16px+env(safe-area-inset-top))] lg:px-8">
      <div className="mb-6">
        <h1 className="text-xl font-semibold tracking-tight">Check-in</h1>
        <div className="mt-1 h-4 w-48 animate-pulse rounded bg-muted" />
      </div>
      <CheckinBoardSkeleton />
    </div>
  )
}
