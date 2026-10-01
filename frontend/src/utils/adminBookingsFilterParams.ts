export type AdminBookingsFilterParams = {
  dateFrom: string
  dateTo: string
  status: string
}

const ALLOWED_STATUSES = new Set([
  'pending',
  'confirmed',
  'in_progress',
  'completed',
  'cancelled',
  'no_show',
  'expired',
])

function normalizeDateParam(value: string | null): string {
  if (!value) {
    return ''
  }
  return /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : ''
}

function normalizeStatusParam(value: string | null): string {
  if (!value) {
    return ''
  }
  return ALLOWED_STATUSES.has(value) ? value : ''
}

/** Read admin bookings list filters from URL search params (deep links). */
export function parseAdminBookingsFilterParams(
  searchParams: URLSearchParams,
): AdminBookingsFilterParams {
  return {
    dateFrom: normalizeDateParam(searchParams.get('date_from')),
    dateTo: normalizeDateParam(searchParams.get('date_to')),
    status: normalizeStatusParam(searchParams.get('status')),
  }
}

/** Build `/admin/bookings` path with salon-day and optional status filter. */
export function buildAdminBookingsFilterPath(
  salonDate: string,
  status?: string,
): string {
  const params = new URLSearchParams()
  params.set('date_from', salonDate)
  params.set('date_to', salonDate)
  if (status && ALLOWED_STATUSES.has(status)) {
    params.set('status', status)
  }
  return `/admin/bookings?${params.toString()}`
}
