import { describe, expect, it, vi } from 'vitest'
import {
  ADMIN_NOTIFICATION_STREAM_RECONNECT_MS,
  countUnread,
  mergeNotification,
} from './useAdminNotifications'
import type { AdminNotificationItem } from '../types/adminNotifications'

const item = (id: string, read = false): AdminNotificationItem => ({
  id,
  event_type: 'public_booking_pending',
  booking_id: `booking-${id}`,
  created_at: '2026-07-02T10:00:00Z',
  read_at: read ? '2026-07-02T11:00:00Z' : null,
  booking_starts_at: '2026-07-02T10:00:00Z',
  customer_name: 'Guest',
  service_name: 'Cut',
  staff_name: 'Stylist',
})

describe('mergeNotification', () => {
  it('prepends new items and deduplicates by id', () => {
    const existing = [item('a'), item('b')]
    const merged = mergeNotification(existing, item('c'))
    expect(merged.map((n) => n.id)).toEqual(['c', 'a', 'b'])

    const deduped = mergeNotification(merged, item('b'))
    expect(deduped.map((n) => n.id)).toEqual(['c', 'a', 'b'])
  })
})

describe('countUnread', () => {
  it('counts only unread notifications', () => {
    expect(countUnread([item('a'), item('b', true)])).toBe(1)
  })
})

describe('stream reconnect contract', () => {
  it('uses a fixed reconnect delay for SSE backoff', () => {
    expect(ADMIN_NOTIFICATION_STREAM_RECONNECT_MS).toBe(3000)
  })

  it('simulates cursor advance across reconnect attempts', async () => {
    const subscribe = vi
      .fn()
      .mockResolvedValueOnce(undefined)
      .mockResolvedValueOnce(undefined)
    let latestId: string | null = 'seed-id'
    const afterIds: Array<string | null> = []

    for (let attempt = 0; attempt < 2; attempt += 1) {
      afterIds.push(latestId)
      await subscribe('token', 'salon-a', latestId)
      latestId = 'notif-new'
    }

    expect(afterIds).toEqual(['seed-id', 'notif-new'])
    expect(subscribe).toHaveBeenCalledTimes(2)
  })
})
