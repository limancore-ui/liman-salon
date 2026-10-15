/**
 * @vitest-environment jsdom
 */
import { afterEach, describe, expect, it } from 'vitest'
import type { ManageBookingSnapshot } from '../types/publicBooking'
import {
  buildManageDeepLink,
  buildManagePagePath,
  ensureManageSessionFromCreate,
  loadManageSnapshot,
  manageStorageKey,
  persistManageSnapshot,
  stripManageTokenFromUrl,
} from './manageBookingStorage'

describe('buildManageDeepLink', () => {
  it('builds full URL with slug, booking id, and token query', () => {
    const url = buildManageDeepLink('my-salon', 'booking-42', 'secret-token')
    expect(url).toBe(
      `${window.location.origin}/s/my-salon/bookings/booking-42/manage?token=secret-token`,
    )
  })

  it('encodeURIComponent slug and booking id in path', () => {
    const url = buildManageDeepLink('salon/name', 'id/with/slash', 't')
    expect(url).toContain('/s/salon%2Fname/bookings/id%2Fwith%2Fslash/manage')
    expect(url).toContain('token=t')
  })
})

describe('buildManagePagePath', () => {
  it('returns path without token', () => {
    expect(buildManagePagePath('slug', 'bid')).toBe('/s/slug/bookings/bid/manage')
  })
})

describe('ensureManageSessionFromCreate', () => {
  afterEach(() => {
    sessionStorage.clear()
  })

  const createResponse = {
    salon_id: 'salon-1',
    customer_id: 'cust-1',
    booking_id: 'b1',
    service_start: '2026-01-01T10:00:00.000Z',
    service_end: '2026-01-01T11:00:00.000Z',
    hold_expires_at: '2026-01-01T12:00:00.000Z',
    manage_token: 'token-from-api',
  }

  it('persists token and booking times when no prior snapshot', () => {
    ensureManageSessionFromCreate('my-salon', createResponse)
    const loaded = loadManageSnapshot('my-salon', 'b1')
    expect(loaded?.token).toBe('token-from-api')
    expect(loaded?.service_start).toBe(createResponse.service_start)
  })

  it('keeps catalog fields from an existing snapshot', () => {
    persistManageSnapshot({
      token: 'old',
      booking_id: 'b1',
      slug: 'my-salon',
      salon_id: 'salon-1',
      service_id: 'svc-9',
      staff_id: 'st-1',
      service_name: 'Стрижка',
      staff_display_name: 'Оля',
      service_start: '2026-01-01T09:00:00.000Z',
      service_end: '2026-01-01T10:00:00.000Z',
      hold_expires_at: '',
    })
    ensureManageSessionFromCreate('my-salon', createResponse)
    const loaded = loadManageSnapshot('my-salon', 'b1')
    expect(loaded?.token).toBe('token-from-api')
    expect(loaded?.service_name).toBe('Стрижка')
    expect(loaded?.staff_display_name).toBe('Оля')
  })
})

describe('loadManageSnapshot', () => {
  afterEach(() => {
    sessionStorage.clear()
  })

  it('returns null when token is empty and booking is not cancelled', () => {
    const snapshot: ManageBookingSnapshot = {
      token: '',
      booking_id: 'b1',
      slug: 'salon',
      salon_id: 's1',
      service_id: 'svc',
      staff_id: 'st',
      service_name: 'Услуга',
      staff_display_name: 'Мастер',
      service_start: '2026-01-01T10:00:00.000Z',
      service_end: '2026-01-01T11:00:00.000Z',
      hold_expires_at: '',
      status: 'confirmed',
    }
    persistManageSnapshot(snapshot)
    expect(loadManageSnapshot('salon', 'b1')).toBeNull()
  })

  it('loads cancelled snapshot without token after reload', () => {
    const snapshot: ManageBookingSnapshot = {
      token: '',
      booking_id: 'b1',
      slug: 'salon',
      salon_id: 's1',
      service_id: 'svc',
      staff_id: 'st',
      service_name: 'Услуга',
      staff_display_name: 'Мастер',
      service_start: '2026-01-01T10:00:00.000Z',
      service_end: '2026-01-01T11:00:00.000Z',
      hold_expires_at: '',
      status: 'cancelled',
      cancelled_at: '2026-01-02T12:00:00.000Z',
    }
    persistManageSnapshot(snapshot)
    const loaded = loadManageSnapshot('salon', 'b1')
    expect(loaded?.status).toBe('cancelled')
    expect(loaded?.token).toBe('')
    expect(
      sessionStorage.getItem(manageStorageKey('salon', 'b1')),
    ).toContain('"status":"cancelled"')
  })
})

describe('stripManageTokenFromUrl', () => {
  afterEach(() => {
    window.history.replaceState(null, '', '/')
  })

  it('removes token from search params without navigation', () => {
    window.history.replaceState(
      null,
      '',
      '/s/demo/bookings/b1/manage?token=abc&foo=bar',
    )
    stripManageTokenFromUrl()
    expect(window.location.pathname).toBe('/s/demo/bookings/b1/manage')
    expect(window.location.search).toBe('?foo=bar')
  })

  it('no-op when token param absent', () => {
    window.history.replaceState(null, '', '/s/demo/bookings/b1/manage?foo=bar')
    stripManageTokenFromUrl()
    expect(window.location.search).toBe('?foo=bar')
  })
})
