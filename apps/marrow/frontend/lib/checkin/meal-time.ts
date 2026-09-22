/** Local midnight for a check-in entry `YYYY-MM-DD`. */
export function entryLocalDate(dateStr: string): Date {
  return new Date(`${dateStr}T00:00:00`)
}

/** Current clock time on the entry's calendar day (for new meal logs). */
export function defaultMealTimeForEntry(dateStr: string, clock: Date = new Date()): Date {
  const d = entryLocalDate(dateStr)
  d.setHours(clock.getHours(), clock.getMinutes(), clock.getSeconds(), clock.getMilliseconds())
  return d
}
