import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { useAdminNotifications } from '../hooks/useAdminNotifications'
import type { AdminNotificationItem } from '../types/adminNotifications'
import {
  ensureAdminNotificationAudioReady,
  isAdminNotificationSoundMuted,
  playAdminNotificationSound,
  setAdminNotificationSoundMuted,
} from '../utils/adminNotificationSound'
import { formatBookingDateTime } from '../utils/adminSalonFormat'

export function AdminNotificationBell() {
  const { session, clearAuthAndRedirect } = useAuth()
  const token = session?.token ?? null
  const salonId = session?.salon?.salon_id ?? null
  const role = session?.salon?.role
  const panelRef = useRef<HTMLDivElement>(null)
  const [soundMuted, setSoundMuted] = useState(isAdminNotificationSoundMuted)

  const onNewRealtimeNotification = useCallback((_item: AdminNotificationItem) => {
    if (soundMuted) {
      return
    }
    void (async () => {
      const ctx = await ensureAdminNotificationAudioReady()
      if (ctx) {
        playAdminNotificationSound(ctx)
      }
    })()
  }, [soundMuted])

  const {
    canUse,
    items,
    unreadCount,
    open,
    setOpen,
    loading,
    markRead,
    markAllRead,
  } = useAdminNotifications({
    token,
    salonId,
    role,
    enabled: session != null,
    onUnauthorized: clearAuthAndRedirect,
    onNewRealtimeNotification,
  })

  useEffect(() => {
    const unlock = () => {
      void ensureAdminNotificationAudioReady()
    }
    window.addEventListener('pointerdown', unlock, { once: true, passive: true })
    window.addEventListener('keydown', unlock, { once: true })
    return () => {
      window.removeEventListener('pointerdown', unlock)
      window.removeEventListener('keydown', unlock)
    }
  }, [])

  const toggleSoundMuted = () => {
    setSoundMuted((prev) => {
      const next = !prev
      setAdminNotificationSoundMuted(next)
      if (!next) {
        void ensureAdminNotificationAudioReady()
      }
      return next
    })
  }

  useEffect(() => {
    if (!open) {
      return
    }
    function onDocClick(event: MouseEvent) {
      if (!panelRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [open, setOpen])

  if (!canUse) {
    return null
  }

  return (
    <div className="admin-notifications" ref={panelRef}>
      <button
        type="button"
        className="admin-notifications__bell btn btn--secondary btn--compact"
        aria-expanded={open}
        aria-haspopup="true"
        aria-label={
          unreadCount > 0
            ? `Notifications, ${unreadCount} unread`
            : 'Notifications'
        }
        onClick={() => {
          void ensureAdminNotificationAudioReady()
          setOpen((v) => !v)
        }}
      >
        <span aria-hidden="true">🔔</span>
        {unreadCount > 0 ? (
          <span className="admin-notifications__badge">{unreadCount}</span>
        ) : null}
      </button>
      {open ? (
        <div className="admin-notifications__panel" role="dialog" aria-label="Notifications">
          <div className="admin-notifications__panel-header">
            <h2 className="admin-notifications__title">Notifications</h2>
            <div className="admin-notifications__panel-actions">
              <button
                type="button"
                className="btn btn--link btn--compact"
                aria-pressed={soundMuted}
                aria-label={soundMuted ? 'Unmute notification sounds' : 'Mute notification sounds'}
                title={soundMuted ? 'Unmute sounds' : 'Mute sounds'}
                onClick={toggleSoundMuted}
              >
                {soundMuted ? 'Sound off' : 'Sound on'}
              </button>
              {unreadCount > 0 ? (
                <button
                  type="button"
                  className="btn btn--link btn--compact"
                  onClick={() => void markAllRead()}
                >
                  Mark all read
                </button>
              ) : null}
            </div>
          </div>
          {loading && items.length === 0 ? (
            <p className="admin-notifications__empty">Loading…</p>
          ) : null}
          {!loading && items.length === 0 ? (
            <p className="admin-notifications__empty">No pending public bookings.</p>
          ) : null}
          <ul className="admin-notifications__list">
            {items.map((item) => {
              const unread = item.read_at == null
              return (
                <li key={item.id} className="admin-notifications__item">
                  <div className="admin-notifications__item-main">
                    <p className="admin-notifications__item-title">
                      {unread ? (
                        <span className="admin-notifications__dot" aria-hidden="true" />
                      ) : null}
                      New public booking
                    </p>
                    <p className="admin-notifications__item-meta">
                      {item.customer_name} · {item.service_name} · {item.staff_name}
                    </p>
                    <p className="admin-notifications__item-time">
                      {formatBookingDateTime(item.booking_starts_at, session?.salon?.timezone)}
                    </p>
                  </div>
                  <div className="admin-notifications__item-actions">
                    <Link
                      to="/admin/bookings"
                      className="btn btn--link btn--compact"
                      onClick={() => {
                        if (unread) {
                          void markRead(item.id)
                        }
                        setOpen(false)
                      }}
                    >
                      View
                    </Link>
                    {unread ? (
                      <button
                        type="button"
                        className="btn btn--link btn--compact"
                        onClick={() => void markRead(item.id)}
                      >
                        Mark read
                      </button>
                    ) : null}
                  </div>
                </li>
              )
            })}
          </ul>
        </div>
      ) : null}
    </div>
  )
}
