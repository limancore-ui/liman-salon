/** Local calendar date as `YYYY-MM-DD`. */
export function toIsoDateLocal(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

export function parseIsoDateLocal(isoDate: string): Date {
  const [y, m, d] = isoDate.split('-').map(Number)
  return new Date(y, m - 1, d)
}

/** Next `count` calendar days starting from today (local). */
export function upcomingLocalDates(count: number): string[] {
  const dates: string[] = []
  const start = new Date()
  start.setHours(0, 0, 0, 0)
  for (let i = 0; i < count; i++) {
    const day = new Date(start)
    day.setDate(start.getDate() + i)
    dates.push(toIsoDateLocal(day))
  }
  return dates
}

/** Calendar date `YYYY-MM-DD` for an instant in the given IANA timezone. */
export function toIsoDateInTimeZone(date: Date, timeZone: string): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date)
}

/** Next `count` distinct calendar days starting from “today” in `timeZone`. */
export function upcomingDatesInTimeZone(count: number, timeZone: string): string[] {
  const dates: string[] = []
  const seen = new Set<string>()
  let cursor = new Date()
  while (dates.length < count) {
    const iso = toIsoDateInTimeZone(cursor, timeZone)
    if (!seen.has(iso)) {
      seen.add(iso)
      dates.push(iso)
    }
    cursor = new Date(cursor.getTime() + 24 * 60 * 60 * 1000)
  }
  return dates
}

export function defaultDateInTimeZone(timeZone: string): string {
  return toIsoDateInTimeZone(new Date(), timeZone)
}
