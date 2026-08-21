import Link from 'next/link'
import { cn, formatDisplayDate } from '@f0rge/ui'
import type { SignalsUnexplained } from '@/lib/api/types/signals'
import { statusText } from '@/lib/ui/status'

interface Props {
  unexplained: SignalsUnexplained
}

function EpisodeList({
  title,
  episodes,
}: {
  title: string
  episodes: SignalsUnexplained['unexplained_bad']
}) {
  if (episodes.length === 0) return null

  return (
    <div>
      <h3 className="mb-1 text-xs font-semibold text-muted-foreground">{title}</h3>
      <ul className="space-y-1.5">
        {episodes.map((ep) => (
          <li
            key={`${ep.start_date}-${ep.end_date}`}
            className="rounded-lg bg-muted/40 px-2 py-1.5 text-xs"
          >
            <span className="font-medium">
              {formatDisplayDate(ep.start_date)}
              {ep.end_date !== ep.start_date
                ? ` – ${formatDisplayDate(ep.end_date)}`
                : ''}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function UnexplainedDays({ unexplained }: Props) {
  const hasContent =
    unexplained.unexplained_bad.length > 0 ||
    unexplained.unexplained_good.length > 0 ||
    unexplained.couldnt_score.length > 0 ||
    unexplained.tracker_proposals.length > 0

  if (!hasContent && !unexplained.relearning) return null

  return (
    <section aria-label="Unexplained days">
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        Unexplained
      </h2>
      <div className="space-y-3 rounded-xl bg-card p-3 ring-1 ring-foreground/10">
        {unexplained.relearning && unexplained.relearning_message ? (
          <p className={cn('text-xs', statusText.warn)}>
            {unexplained.relearning_message}
          </p>
        ) : null}
        <EpisodeList title="Worse than expected" episodes={unexplained.unexplained_bad} />
        <EpisodeList title="Better than expected" episodes={unexplained.unexplained_good} />
        {unexplained.couldnt_score.length > 0 && (
          <div>
            <h3 className="mb-1 text-xs font-semibold text-muted-foreground">
              Couldn&apos;t score
            </h3>
            <p className="text-xs text-muted-foreground">
              {unexplained.couldnt_score.map(formatDisplayDate).join(', ')}
            </p>
          </div>
        )}
        {unexplained.tracker_proposals.length > 0 && (
          <div>
            <h3 className="mb-1 text-xs font-semibold text-muted-foreground">
              Suggested trackers
            </h3>
            <ul className="space-y-1 text-xs">
              {unexplained.tracker_proposals.map((t) => (
                <li key={t.tracker_id}>
                  <Link
                    href="/customize/trackers"
                    className="font-medium text-foreground underline-offset-4 hover:underline"
                  >
                    {t.label}
                  </Link>
                  <span className="text-muted-foreground">
                    {' '}
                    ({t.days_covered} days)
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  )
}
