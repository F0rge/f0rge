import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Local calendar date as YYYY-MM-DD. Use this instead of
// `date.toISOString().split('T')[0]`, which reads the UTC date and is
// wrong for local users between midnight and their UTC offset (e.g. until
// ~2am in Luxembourg).
export function formatLocalDate(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

// en-GB "12 Jan 2026" display formatting for a YYYY-MM-DD date string.
export function formatDisplayDate(dateStr: string): string {
  const date = new Date(dateStr + "T00:00:00")
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })
}

// en-GB "12 Jul 2026, 18:50" for ISO datetimes from the API.
export function formatDisplayDateTime(dateTimeStr: string): string {
  const date = new Date(dateTimeStr)
  if (Number.isNaN(date.getTime())) return dateTimeStr
  return date.toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

// Current local wall-clock time as "HH:MM" (zero-padded, no tz logic).
export function nowHHMM(): string {
  const now = new Date()
  return `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`
}
