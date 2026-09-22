import { Card, CardContent, cn } from '@f0rge/ui'

function CheckinCardSkeleton({
  className,
  contentLines = 2,
}: {
  className?: string
  contentLines?: number
}) {
  return (
    <Card className={cn('h-full', className)}>
      <CardContent className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div className="h-4 w-24 animate-pulse rounded bg-muted" />
          <div className="h-5 w-14 animate-pulse rounded-full bg-muted" />
        </div>
        {Array.from({ length: contentLines }, (_, i) => (
          <div key={i} className="h-10 w-full animate-pulse rounded-xl bg-muted" />
        ))}
      </CardContent>
    </Card>
  )
}

/** Placeholder grid matching the check-in board layout while entry data loads. */
export function CheckinBoardSkeleton() {
  return (
    <div className="space-y-4 pb-8" aria-busy="true" aria-label="Loading check-in">
      <div className="grid grid-cols-12 gap-4 auto-rows-min">
        <div className="col-span-12">
          <CheckinCardSkeleton contentLines={1} />
        </div>
        <div className="col-span-12">
          <CheckinCardSkeleton contentLines={3} />
        </div>
        <div className="col-span-12 lg:col-span-4">
          <CheckinCardSkeleton />
        </div>
        <div className="col-span-12 lg:col-span-4">
          <CheckinCardSkeleton />
        </div>
        <div className="col-span-12 lg:col-span-4">
          <CheckinCardSkeleton />
        </div>
        <div className="col-span-12 lg:col-span-6">
          <CheckinCardSkeleton />
        </div>
        <div className="col-span-12 lg:col-span-6">
          <CheckinCardSkeleton />
        </div>
      </div>
    </div>
  )
}
