'use client'

interface FetchErrorProps {
  message?: string
  onRetry?: () => void
}

export function FetchError({
  message = 'Failed to load data.',
  onRetry,
}: FetchErrorProps) {
  return (
    <div className="flex flex-col items-center gap-3 py-12 text-center">
      <p className="text-sm text-destructive">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-lg border border-border px-4 py-2 text-sm font-medium transition-colors hover:bg-muted"
        >
          Retry
        </button>
      )}
    </div>
  )
}
