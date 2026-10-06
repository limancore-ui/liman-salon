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

type UseAdminNotificationsArgs = {
  token: string | null
  salonId: string | null
  role: string | undefined
  enabled: boolean
  onUnauthorized?: () => void
}

export function useAdminNotifications({
  token,
  salonId,
  role,
  enabled,
  onUnauthorized,
}: UseAdminNotificationsArgs) {
  const [items, setItems] = useState<AdminNotificationItem[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const latestIdRef = useRef<string | null>(null)

  const canUse = enabled && Boolean(token && salonId) && (role === 'owner' || role === 'admin')

  const refresh = useCallback(async () => {
    if (!canUse || !token || !salonId) {
      return
    }
    setLoading(true)
    try {
      const list = await fetchAdminNotifications(token, salonId, { limit: 50 })
      setItems(list.items)
      setUnreadCount(list.unread_count)
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
                latestIdRef.current = item.id
                setItems((prev) => mergeNotification(prev, item))
                setUnreadCount((prev) => prev + (item.read_at == null ? 1 : 0))
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
