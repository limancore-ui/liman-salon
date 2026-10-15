import type {
  ManageBookingSnapshot,
  PublicBookingCreateResponse,
} from '../types/publicBooking'

const KEY_PREFIX = 'liman:public-manage:'

export function manageStorageKey(slug: string, bookingId: string): string {
  return `${KEY_PREFIX}${slug}:${bookingId}`
}

function isCancelledManageSnapshot(snapshot: ManageBookingSnapshot): boolean {
  return (
    snapshot.status === 'cancelled' ||
    Boolean(snapshot.cancelled_at?.trim())
  )
}

export function loadManageSnapshot(
  slug: string,
  bookingId: string,
): ManageBookingSnapshot | null {
  try {
    const raw = sessionStorage.getItem(manageStorageKey(slug, bookingId))
    if (!raw) {
      return null
    }
    const parsed = JSON.parse(raw) as ManageBookingSnapshot
    if (typeof parsed.token !== 'string') {
      return null
    }
    if (!parsed.token.trim()) {
      return isCancelledManageSnapshot(parsed) ? parsed : null
    }
    return parsed
  } catch {
    return null
  }
}

export function persistManageSnapshot(
  snapshot: ManageBookingSnapshot,
): ManageBookingSnapshot {
  sessionStorage.setItem(
    manageStorageKey(snapshot.slug, snapshot.booking_id),
    JSON.stringify(snapshot),
  )
  return snapshot
}

export function clearManageSnapshot(slug: string, bookingId: string): void {
  try {
    sessionStorage.removeItem(manageStorageKey(slug, bookingId))
  } catch {
    /* ignore storage errors */
  }
}

/** Remove manage token from the URL without navigation. */
export function stripManageTokenFromUrl(): void {
  const url = new URL(window.location.href)
  if (!url.searchParams.has('token')) {
    return
  }
  url.searchParams.delete('token')
  const search = url.searchParams.toString()
  const next = url.pathname + (search ? `?${search}` : '') + url.hash
  window.history.replaceState(window.history.state, '', next)
}

export function buildManagePagePath(slug: string, bookingId: string): string {
  return `/s/${encodeURIComponent(slug)}/bookings/${encodeURIComponent(bookingId)}/manage`
}

export function buildManageDeepLink(
  slug: string,
  bookingId: string,
  token: string,
): string {
  const path = buildManagePagePath(slug, bookingId)
  const query = new URLSearchParams({ token })
  return `${window.location.origin}${path}?${query.toString()}`
}

/** Merge POST /bookings manage_token into session before same-tab manage navigation. */
export function ensureManageSessionFromCreate(
  slug: string,
  booking: PublicBookingCreateResponse,
): ManageBookingSnapshot {
  const existing = loadManageSnapshot(slug, booking.booking_id)
  return persistManageSnapshot({
    token: booking.manage_token,
    booking_id: booking.booking_id,
    slug,
    salon_id: booking.salon_id,
    service_id: existing?.service_id ?? '',
    staff_id: existing?.staff_id ?? '',
    service_name: existing?.service_name ?? '',
    staff_display_name: existing?.staff_display_name ?? '',
    service_start: booking.service_start,
    service_end: booking.service_end,
    hold_expires_at: booking.hold_expires_at,
    status: existing?.status,
    cancelled_at: existing?.cancelled_at,
    can_cancel: existing?.can_cancel,
    can_reschedule: existing?.can_reschedule,
  })
}
