import type { ManageBookingSnapshot } from '../types/publicBooking'

const KEY_PREFIX = 'liman:public-manage:'

export function manageStorageKey(slug: string, bookingId: string): string {
  return `${KEY_PREFIX}${slug}:${bookingId}`
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
    if (typeof parsed.token !== 'string' || !parsed.token.trim()) {
      return null
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
