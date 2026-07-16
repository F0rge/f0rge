'use client'

import { useEntryStats } from '@/lib/api/hooks'

const DAY_LETTERS = ['M', 'T', 'W', 'T', 'F', 'S', 'S']

/** "This week" strip: one dot per day, Mon→Sun, today ringed. */
export function ConsistencyRow() {
  const weekDays = useEntryStats().data?.week_days
  if (weekDays == null) return null

  const done = weekDays.filter(Boolean).length
  // week_days is Monday-0; JS getDay() is Sunday-0.
  const todayIdx = (new Date().getDay() + 6) % 7

  return (
    <section>
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
          This week
        </h2>
        <p className="text-[12px] text-muted-foreground">
          <b className="font-bold tabular-nums text-foreground">{done} of 7</b> days checked in
        </p>
      </div>
      {/* The header line carries the information; the dots are decoration. */}
      <div className="mt-2 grid grid-cols-7" aria-hidden>
        {DAY_LETTERS.map((letter, i) => (
          <div key={i} className="flex flex-col items-center gap-1">
            <span
              className="flex size-[26px] items-center justify-center rounded-full bg-muted"
              // --marrow-* isn't mapped into @theme, so the brand ring can't be a utility.
              style={i === todayIdx ? { boxShadow: '0 0 0 1.5px var(--marrow-nucleus)' } : undefined}
            >
              {weekDays[i] && (
                <span
                  className="size-2.5 rounded-full"
                  style={{ background: 'var(--marrow-nucleus)' }}
                />
              )}
            </span>
            <span className="text-[10px] text-muted-foreground">{letter}</span>
          </div>
        ))}
      </div>
    </section>
  )
}
