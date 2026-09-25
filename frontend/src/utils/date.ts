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
