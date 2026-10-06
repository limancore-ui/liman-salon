import { afterEach, describe, expect, it, vi } from 'vitest'
import { subscribeAdminNotificationStream } from './adminNotifications'
import type { AdminNotificationItem } from '../types/adminNotifications'

const salonId = 'salon-a'
const token = 'test-token'

const sampleItem: AdminNotificationItem = {
  id: 'notif-1',
  event_type: 'public_booking_pending',
  booking_id: 'booking-1',
  created_at: '2026-07-02T10:00:00Z',
  read_at: null,
  booking_starts_at: '2026-07-02T10:00:00Z',
  customer_name: 'Guest',
  service_name: 'Cut',
  staff_name: 'Stylist',
}

function encodeSse(parts: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  let index = 0
  return new ReadableStream({
    pull(controller) {
      if (index >= parts.length) {
        controller.close()
        return
      }
      controller.enqueue(encoder.encode(parts[index]))
      index += 1
    },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('subscribeAdminNotificationStream', () => {
  it('parses data events and ignores heartbeat comments', async () => {
    const payload = JSON.stringify({
      type: 'notification',
      notification: sampleItem,
    })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: encodeSse([`: heartbeat\n\n`, `data: ${payload}\n\n`]),
      }),
    )

    const seen: AdminNotificationItem[] = []
    await subscribeAdminNotificationStream(token, salonId, null, {
      onNotification: (item) => {
        seen.push(item)
      },
    }, new AbortController().signal)

    expect(seen).toEqual([sampleItem])
    expect(fetch).toHaveBeenCalledWith(
      `/api/v1/salons/${salonId}/admin-notifications/stream`,
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: `Bearer ${token}`,
          Accept: 'text/event-stream',
        }),
      }),
    )
  })

  it('buffers partial chunks until event delimiter', async () => {
    const payload = JSON.stringify({
      type: 'notification',
      notification: sampleItem,
    })
    const full = `data: ${payload}\n\n`
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: encodeSse([full.slice(0, 12), full.slice(12)]),
      }),
    )

    const seen: AdminNotificationItem[] = []
    await subscribeAdminNotificationStream(token, salonId, null, {
      onNotification: (item) => {
        seen.push(item)
      },
    }, new AbortController().signal)

    expect(seen).toEqual([sampleItem])
  })

  it('sends after_id on reconnect cursor', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: encodeSse([]),
      }),
    )

    await subscribeAdminNotificationStream(
      token,
      salonId,
      'cursor-id',
      { onNotification: () => {} },
      new AbortController().signal,
    )

    expect(fetch).toHaveBeenCalledWith(
      `/api/v1/salons/${salonId}/admin-notifications/stream?after_id=cursor-id`,
      expect.any(Object),
    )
  })

  it('throws ApiError when stream request is unauthorized', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
        json: async () => ({ detail: 'Unauthorized' }),
      }),
    )

    await expect(
      subscribeAdminNotificationStream(
        token,
        salonId,
        null,
        { onNotification: () => {} },
        new AbortController().signal,
      ),
    ).rejects.toMatchObject({ status: 401 })
  })
})
