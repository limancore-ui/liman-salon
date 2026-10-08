import { afterEach, describe, expect, it, vi } from 'vitest'
import { createAdminBooking } from './bookings'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('createAdminBooking', () => {
  it('POSTs unchanged admin booking create contract', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 'booking-1' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await createAdminBooking('token', 'salon-1', {
      customer_id: 'cust-1',
      staff_id: 'staff-1',
      service_id: 'svc-1',
      requested_service_start: '2026-09-25T09:00:00.000Z',
      source: 'admin',
      status: 'confirmed',
    })

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/salons/salon-1/bookings', {
      method: 'POST',
      headers: {
        Authorization: 'Bearer token',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        customer_id: 'cust-1',
        staff_id: 'staff-1',
        service_id: 'svc-1',
        requested_service_start: '2026-09-25T09:00:00.000Z',
        source: 'admin',
        status: 'confirmed',
      }),
    })
  })
})
