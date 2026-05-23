/**
 * treatment-day.ts — computes the 1-based "day N" number for an active treatment.
 *
 * Extracted verbatim from checkin-form.tsx:462-465.
 * Both dates are YYYY-MM-DD strings; noon-anchored to dodge DST edge cases.
 */

export function getTreatmentDayNum(startDate: string, checkinDate: string): number {
  const start = new Date(startDate + 'T12:00:00')
  const current = new Date(checkinDate + 'T12:00:00')
  return Math.floor((current.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)) + 1
}
