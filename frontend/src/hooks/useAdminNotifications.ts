import { useCallback, useEffect, useRef, useState } from 'react'
import {
  fetchAdminNotifications,
  markAdminNotificationRead,
  markAllAdminNotificationsRead,
  subscribeAdminNotificationStream,
} from '../api/adminNotifications'
import { isUnauthorizedError } from '../api/auth'
import type { AdminNotificationItem } from '../types/adminNotifications'

export const ADMIN_NOTIFICATION_STREAM_RECONNECT_MS = 3000

export function mergeNotification(
  prev: AdminNotificationItem[],
  item: AdminNotificationItem,
): AdminNotificationItem[] {
  if (prev.some((n) => n.id === item.id)) {
    return prev
  }
  return [item, ...prev]
}

export function countUnread(items: AdminNotificationItem[]): number {
  return items.filter((n) => n.read_at == null).length
}

export type ApplyStreamNotificationResult = {
  items: AdminNotificationItem[]
  unreadCount: number
  latestId: string | null
}

/** Applies one SSE notification to list + unread cursor state (pure, for hook + tests). */
export function applyStreamNotification(
  prevItems: AdminNotificationItem[],
  unreadCount: number,
  item: AdminNotificationItem,
): ApplyStreamNotificationResult {
  const next = mergeNotification(prevItems, item)
  if (next === prevItems) {
    return { items: prevItems, unreadCount, latestId: null }
  }
  return {
    items: next,
    unreadCount: item.read_at == null ? unreadCount + 1 : unreadCount,
    latestId: item.id,
  }
}

/** True when an in-flight refresh snapshot may still be applied to state. */
export function shouldApplyRefreshSnapshot(
  snapshotGeneration: number,
  currentGeneration: number,
): boolean {
  return snapshotGeneration === currentGeneration
}

/** True when SSE added a notification id not already in list state (UI callback once per id). */
export function isNewRealtimeStreamNotification(
  result: ApplyStreamNotificationResult,
): boolean {
  return result.latestId != null
}

/** Plan SSE apply + sound callback from a ref snapshot (never call inside setState updaters). */
export function planStreamNotificationFromSnapshot(
  items: AdminNotificationItem[],
  unreadCount: number,
  item: AdminNotificationItem,
): ApplyStreamNotificationResult & { notifyNew: boolean } {
  const result = applyStreamNotification(items, unreadCount, item)
  return {
    ...result,
    notifyNew: isNewRealtimeStreamNotification(result),
  }
}

type UseAdminNotificationsArgs = {
  token: string | null
  salonId: string | null
  role: string | undefined
  enabled: boolean
  onUnauthorized?: () => void
  onNewRealtimeNotification?: (item: AdminNotificationItem) => void
}

export function useAdminNotifications({
  token,
  salonId,
  role,
  enabled,
  onUnauthorized,
  onNewRealtimeNotification,
}: UseAdminNotificationsArgs) {
  const [items, setItems] = useState<AdminNotificationItem[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const latestIdRef = useRef<string | null>(null)
  const itemsRef = useRef<AdminNotificationItem[]>([])
  const unreadCountRef = useRef(0)
  const refreshGenerationRef = useRef(0)
  const onNewRealtimeNotificationRef = useRef(onNewRealtimeNotification)

  const canUse = enabled && Boolean(token && salonId) && (role === 'owner' || role === 'admin')

  useEffect(() => {
    onNewRealtimeNotificationRef.current = onNewRealtimeNotification
  }, [onNewRealtimeNotification])

  useEffect(() => {
    itemsRef.current = items
  }, [items])

  useEffect(() => {
    unreadCountRef.current = unreadCount
  }, [unreadCount])

  const refresh = useCallback(async () => {
    if (!canUse || !token || !salonId) {
      return
    }
    const snapshotGeneration = ++refreshGenerationRef.current
    setLoading(true)
    try {
      const list = await fetchAdminNotifications(token, salonId, { limit: 50 })
      if (
        !shouldApplyRefreshSnapshot(snapshotGeneration, refreshGenerationRef.current)
      ) {
        return
      }
      setItems(list.items)
      itemsRef.current = list.items
      setUnreadCount(list.unread_count)
      unreadCountRef.current = list.unread_count
      if (list.items.length > 0) {
        latestIdRef.current = list.items[0].id
      }
    } catch (err) {
      if (isUnauthorizedError(err)) {
        onUnauthorized?.()
      }
    } finally {
      setLoading(false)
    }
  }, [canUse, token, salonId, onUnauthorized])

  useEffect(() => {
    if (!canUse) {
      setItems([])
      setUnreadCount(0)
      return
    }
    void refresh()
  }, [canUse, refresh, salonId])

  useEffect(() => {
    if (!canUse || !token || !salonId) {
      return
    }

    let cancelled = false
    let activeController: AbortController | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null

    const sleep = (ms: number) =>
      new Promise<void>((resolve) => {
        reconnectTimer = setTimeout(resolve, ms)
      })

    const runStream = async () => {
      while (!cancelled) {
        activeController = new AbortController()
        try {
          await subscribeAdminNotificationStream(
            token,
            salonId,
            latestIdRef.current,
            {
              onNotification: (item) => {
                refreshGenerationRef.current += 1
                const snapshotUnread = unreadCountRef.current
                const planned = planStreamNotificationFromSnapshot(
                  itemsRef.current,
                  snapshotUnread,
                  item,
                )
                itemsRef.current = planned.items
                if (planned.latestId != null) {
                  latestIdRef.current = planned.latestId
                }
                setItems((prev) => {
                  const applied = applyStreamNotification(
                    prev,
                    snapshotUnread,
                    item,
                  )
                  itemsRef.current = applied.items
                  if (applied.latestId != null) {
                    latestIdRef.current = applied.latestId
                  }
                  unreadCountRef.current = applied.unreadCount
                  return applied.items
                })
                if (planned.notifyNew) {
                  onNewRealtimeNotificationRef.current?.(item)
                }
                if (planned.unreadCount !== snapshotUnread) {
                  unreadCountRef.current = planned.unreadCount
                  setUnreadCount(planned.unreadCount)
                }
              },
            },
            activeController.signal,
          )
        } catch (err) {
          if (cancelled || activeController.signal.aborted) {
            return
          }
          if (isUnauthorizedError(err)) {
            onUnauthorized?.()
            return
          }
        }
        if (cancelled) {
          return
        }
        await sleep(ADMIN_NOTIFICATION_STREAM_RECONNECT_MS)
      }
    }

    void runStream()

    return () => {
      cancelled = true
      activeController?.abort()
      if (reconnectTimer != null) {
        clearTimeout(reconnectTimer)
      }
    }
  }, [canUse, token, salonId, onUnauthorized])

  const markRead = useCallback(
    async (notificationId: string) => {
      if (!token || !salonId) {
        return
      }
      await markAdminNotificationRead(token, salonId, notificationId)
      setItems((prev) =>
        prev.map((n) =>
          n.id === notificationId
            ? { ...n, read_at: n.read_at ?? new Date().toISOString() }
            : n,
        ),
      )
      setUnreadCount((prev) => Math.max(0, prev - 1))
    },
    [token, salonId],
  )

  const markAllRead = useCallback(async () => {
    if (!token || !salonId) {
      return
    }
    await markAllAdminNotificationsRead(token, salonId)
    const now = new Date().toISOString()
    setItems((prev) => prev.map((n) => ({ ...n, read_at: n.read_at ?? now })))
    setUnreadCount(0)
  }, [token, salonId])

  return {
    canUse,
    items,
    unreadCount,
    open,
    setOpen,
    loading,
    refresh,
    markRead,
    markAllRead,
    localUnread: countUnread(items),
  }
}
