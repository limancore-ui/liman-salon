/** Salon-local wall clock ↔ UTC for admin booking create, reschedule, and list filters. */

function timeZoneOffsetMs(timeZone: string, instant: Date): number {
  const dtf = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    dtf.formatToParts(instant).find((p) => p.type === type)?.value ?? '0'
  const asUtc = Date.UTC(
    Number(part('year')),
    Number(part('month')) - 1,
    Number(part('day')),
    Number(part('hour')),
    Number(part('minute')),
    Number(part('second')),
  )
  return asUtc - instant.getTime()
}

/** Interpret `datetime-local` wall time in salon IANA timezone; return UTC ISO. */
export function salonLocalDateTimeToIso(value: string, timeZone: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(value)
  if (!match) {
    return new Date(value).toISOString()
  }
  const [, y, mo, d, h, mi] = match
  const wallUtc = Date.UTC(Number(y), Number(mo) - 1, Number(d), Number(h), Number(mi), 0)
  let utcMs = wallUtc
  for (let i = 0; i < 4; i++) {
    utcMs = wallUtc - timeZoneOffsetMs(timeZone, new Date(utcMs))
  }
  return new Date(utcMs).toISOString()
}

/** Format instant as `datetime-local` value in salon IANA timezone. */
export function isoToSalonLocalDatetimeLocal(iso: string, timeZone: string): string {
  const instant = new Date(iso)
  const dtf = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    dtf.formatToParts(instant).find((p) => p.type === type)?.value ?? '00'
  let hour = part('hour')
  if (hour === '24') {
    hour = '00'
  }
  return `${part('year')}-${part('month')}-${part('day')}T${hour}:${part('minute')}`
}

/** Add one calendar day to `YYYY-MM-DD` (date-only, no timezone). */
export function addCalendarDay(isoDate: string): string {
  const [y, mo, d] = isoDate.split('-').map(Number)
  const next = new Date(Date.UTC(y, mo - 1, d))
  next.setUTCDate(next.getUTCDate() + 1)
  const year = next.getUTCFullYear()
  const month = String(next.getUTCMonth() + 1).padStart(2, '0')
  const day = String(next.getUTCDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/**
 * Map salon-local calendar dates (dashboard `salon_date`, filter inputs) to UTC
 * `starts_at_from` / `starts_at_to` for list API (`starts_at` half-open range).
 */
export function salonLocalDateRangeToUtcIso(
  from: string,
  to: string,
  timeZone: string,
): {
  starts_at_from?: string
  starts_at_to?: string
} {
  const range: { starts_at_from?: string; starts_at_to?: string } = {}
  if (from) {
    range.starts_at_from = salonLocalDateTimeToIso(`${from}T00:00`, timeZone)
  }
  if (to) {
    const endExclusive = addCalendarDay(to)
    range.starts_at_to = salonLocalDateTimeToIso(`${endExclusive}T00:00`, timeZone)
  }
  return range
}
