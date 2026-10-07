import { describe, expect, it, vi } from 'vitest'
import {
  ADMIN_NOTIFICATION_STREAM_RECONNECT_MS,
  applyStreamNotification,
  countUnread,
  isNewRealtimeStreamNotification,
  mergeNotification,
  shouldApplyRefreshSnapshot,
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

describe('applyStreamNotification', () => {
  it('does not change unread when duplicate id is replayed', () => {
    const items = [item('a'), item('b')]
    const result = applyStreamNotification(items, 2, item('b'))
    expect(result.items).toBe(items)
    expect(result.unreadCount).toBe(2)
    expect(result.latestId).toBeNull()
  })

  it('increments unread by one for a new unread notification', () => {
    const items = [item('a')]
    const result = applyStreamNotification(items, 1, item('c'))
    expect(result.items.map((n) => n.id)).toEqual(['c', 'a'])
    expect(result.unreadCount).toBe(2)
    expect(result.latestId).toBe('c')
  })

  it('does not increase unreadCount for a new already-read notification', () => {
    const items = [item('a')]
    const result = applyStreamNotification(items, 1, item('c', true))
    expect(result.items.map((n) => n.id)).toEqual(['c', 'a'])
    expect(result.unreadCount).toBe(1)
    expect(result.latestId).toBe('c')
  })

  it('keeps unread at 3 when three known ids are replayed', () => {
    let items = [item('1'), item('2'), item('3')]
    let unread = 3
    for (const id of ['1', '2', '3']) {
      const result = applyStreamNotification(items, unread, item(id))
      items = result.items
      unread = result.unreadCount
    }
    expect(unread).toBe(3)
    expect(items.map((n) => n.id)).toEqual(['1', '2', '3'])
  })
})

describe('isNewRealtimeStreamNotification', () => {
  it('is false for duplicate SSE replay (no UI callback)', () => {
    const items = [item('a'), item('b')]
    const result = applyStreamNotification(items, 2, item('b'))
    expect(isNewRealtimeStreamNotification(result)).toBe(false)
  })

  it('is true once for a new SSE notification id', () => {
    const items = [item('a')]
    const result = applyStreamNotification(items, 1, item('new'))
    expect(isNewRealtimeStreamNotification(result)).toBe(true)
  })

  it('stays false when the same ids are replayed after reconnect', () => {
    let items = [item('1'), item('2')]
    let unread = 2
    const seen: boolean[] = []
    for (const id of ['1', '2', '3', '3', '1']) {
      const result = applyStreamNotification(items, unread, item(id))
      seen.push(isNewRealtimeStreamNotification(result))
      items = result.items
      unread = result.unreadCount
    }
    expect(seen).toEqual([false, false, true, false, false])
  })
})

describe('shouldApplyRefreshSnapshot', () => {
  it('allows apply when generation unchanged (no SSE during refresh)', () => {
    expect(shouldApplyRefreshSnapshot(2, 2)).toBe(true)
  })

  it('blocks apply when SSE bumped generation during refresh', () => {
    const snapshotAtRefreshStart = 1
    let currentGeneration = 1
    expect(shouldApplyRefreshSnapshot(snapshotAtRefreshStart, currentGeneration)).toBe(
      true,
    )
    currentGeneration += 1
    expect(shouldApplyRefreshSnapshot(snapshotAtRefreshStart, currentGeneration)).toBe(
      false,
    )
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
