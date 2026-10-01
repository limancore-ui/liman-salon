import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { AdminLayout } from '../components/AdminLayout'
import { useAuth } from '../auth/AuthContext'
import {
  cancelAdminBooking,
  fetchAdminBookings,
  rescheduleAdminBooking,
} from '../api/bookings'
import { fetchAdminStaff } from '../api/staff'
import { ApiError } from '../api/errors'
import { isUnauthorizedError } from '../api/auth'
import type { BookingListItem } from '../types/bookings'
import type { StaffListItem } from '../types/staff'
import {
  isAdminBookingSlotConflictError,
  mapAdminBookingActionError,
} from '../utils/mapAdminBookingActionError'

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'pending', label: 'Pending' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
  { value: 'no_show', label: 'No show' },
  { value: 'expired', label: 'Expired' },
] as const

type BookingActionMode = 'cancel' | 'reschedule'

function canManageBookings(role: string | undefined): boolean {
  return role === 'owner' || role === 'admin'
}

function isActionableBookingStatus(status: string): boolean {
  return status === 'pending' || status === 'confirmed'
}

function formatDateTime(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

function formatPrice(cents: number): string {
  return (cents / 100).toLocaleString(undefined, {
    style: 'currency',
    currency: 'KZT',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })
}

function dateInputToUtcRange(from: string, to: string): {
  starts_at_from?: string
  starts_at_to?: string
} {
  const range: { starts_at_from?: string; starts_at_to?: string } = {}
  if (from) {
    range.starts_at_from = `${from}T00:00:00.000Z`
  }
  if (to) {
    const end = new Date(`${to}T00:00:00.000Z`)
    end.setUTCDate(end.getUTCDate() + 1)
    range.starts_at_to = end.toISOString()
  }
  return range
}

function timeZoneOffsetMs(timeZone: string, instant: Date): number {
  const dtf = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    dtf.formatToParts(instant).find((p) => p.type === type)?.value ?? '0'
  const asUtc = Date.UTC(
    Number(part('year')),
    Number(part('month')) - 1,
    Number(part('day')),
    Number(part('hour')),
    Number(part('minute')),
    Number(part('second')),
  )
  return asUtc - instant.getTime()
}

/** Interpret `datetime-local` wall time in salon IANA timezone; return UTC ISO. */
function datetimeLocalToIso(value: string, timeZone: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(value)
  if (!match) {
    return new Date(value).toISOString()
  }
  const [, y, mo, d, h, mi] = match
  const wallUtc = Date.UTC(Number(y), Number(mo) - 1, Number(d), Number(h), Number(mi), 0)
  let utcMs = wallUtc
  for (let i = 0; i < 4; i++) {
    utcMs = wallUtc - timeZoneOffsetMs(timeZone, new Date(utcMs))
  }
  return new Date(utcMs).toISOString()
}

/** Format instant as `datetime-local` value in salon IANA timezone. */
function isoToDatetimeLocal(iso: string, timeZone: string): string {
  const instant = new Date(iso)
  const dtf = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    dtf.formatToParts(instant).find((p) => p.type === type)?.value ?? '00'
  let hour = part('hour')
  if (hour === '24') {
    hour = '00'
  }
  return `${part('year')}-${part('month')}-${part('day')}T${hour}:${part('minute')}`
}

function resolveStaffIdForBooking(
  staffList: StaffListItem[],
  staffName: string,
): string {
  const match = staffList.find((row) => row.display_name === staffName)
  if (match) {
    return match.id
  }
  const bookable = staffList.find((row) => row.is_bookable && row.is_active)
  return bookable?.id ?? staffList[0]?.id ?? ''
}

export function AdminBookingsPage() {
  const { session, clearAuthAndRedirect } = useAuth()
  const [items, setItems] = useState<BookingListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [status, setStatus] = useState('')

  const [staffList, setStaffList] = useState<StaffListItem[]>([])
  const [staffLoading, setStaffLoading] = useState(false)

  const [actionBooking, setActionBooking] = useState<BookingListItem | null>(null)
  const [actionMode, setActionMode] = useState<BookingActionMode | null>(null)
  const [cancelReason, setCancelReason] = useState('')
  const [rescheduleStaffId, setRescheduleStaffId] = useState('')
  const [rescheduleStartLocal, setRescheduleStartLocal] = useState('')
  const [actionSubmitting, setActionSubmitting] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const manage = canManageBookings(session?.salon.role)
  const salonTimeZone = session?.salon.timezone ?? 'UTC'

  const clearAction = useCallback(() => {
    setActionBooking(null)
    setActionMode(null)
    setCancelReason('')
    setRescheduleStaffId('')
    setRescheduleStartLocal('')
    setActionError(null)
  }, [])

  const load = useCallback(async () => {
    if (!session) {
      return
    }
    setLoading(true)
    setError(null)
    try {
      const range = dateInputToUtcRange(dateFrom, dateTo)
      const rows = await fetchAdminBookings(session.token, session.salon.salon_id, {
        ...range,
        status: status || undefined,
        limit: 100,
      })
      setItems(rows)
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError('Could not load bookings.')
      }
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [session, dateFrom, dateTo, status, clearAuthAndRedirect])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (!session || !manage) {
      setStaffList([])
      return
    }

    let cancelled = false
    setStaffLoading(true)
    fetchAdminStaff(session.token, session.salon.salon_id, {
      active_only: true,
      bookable_only: true,
    })
      .then((rows) => {
        if (!cancelled) {
          setStaffList(rows)
        }
      })
      .catch((err: unknown) => {
        if (cancelled) {
          return
        }
        if (isUnauthorizedError(err)) {
          clearAuthAndRedirect()
          return
        }
        setStaffList([])
      })
      .finally(() => {
        if (!cancelled) {
          setStaffLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [session, manage, clearAuthAndRedirect])

  const startCancel = useCallback((row: BookingListItem) => {
    setActionError(null)
    setActionBooking(row)
    setActionMode('cancel')
    setCancelReason('')
  }, [])

  const startReschedule = useCallback(
    (row: BookingListItem) => {
      setActionError(null)
      setActionBooking(row)
      setActionMode('reschedule')
      setRescheduleStaffId(resolveStaffIdForBooking(staffList, row.staff_name))
      setRescheduleStartLocal(isoToDatetimeLocal(row.starts_at, salonTimeZone))
    },
    [staffList, salonTimeZone],
  )

  const handleConfirmCancel = useCallback(
    async (event: FormEvent) => {
      event.preventDefault()
      if (!session || !actionBooking || actionSubmitting) {
        return
      }
      setActionSubmitting(true)
      setActionError(null)
      try {
        await cancelAdminBooking(
          session.token,
          session.salon.salon_id,
          actionBooking.id,
          { reason: cancelReason.trim() || undefined },
        )
        clearAction()
        await load()
      } catch (err: unknown) {
        if (isUnauthorizedError(err)) {
          clearAuthAndRedirect()
          return
        }
        setActionError(mapAdminBookingActionError(err))
      } finally {
        setActionSubmitting(false)
      }
    },
    [
      session,
      actionBooking,
      actionSubmitting,
      cancelReason,
      clearAction,
      load,
      clearAuthAndRedirect,
    ],
  )

  const handleConfirmReschedule = useCallback(
    async (event: FormEvent) => {
      event.preventDefault()
      if (!session || !actionBooking || actionSubmitting) {
        return
      }
      if (!rescheduleStaffId) {
        setActionError('Select a staff member.')
        return
      }
      if (!rescheduleStartLocal) {
        setActionError('Choose a new service start time.')
        return
      }

      setActionSubmitting(true)
      setActionError(null)
      try {
        await rescheduleAdminBooking(
          session.token,
          session.salon.salon_id,
          actionBooking.id,
          {
            staff_id: rescheduleStaffId,
            service_start: datetimeLocalToIso(rescheduleStartLocal, salonTimeZone),
          },
        )
        clearAction()
        await load()
      } catch (err: unknown) {
        if (isUnauthorizedError(err)) {
          clearAuthAndRedirect()
          return
        }
        setActionError(mapAdminBookingActionError(err))
        if (isAdminBookingSlotConflictError(err)) {
          setRescheduleStartLocal('')
        }
      } finally {
        setActionSubmitting(false)
      }
    },
    [
      session,
      actionBooking,
      actionSubmitting,
      rescheduleStaffId,
      rescheduleStartLocal,
      salonTimeZone,
      clearAction,
      load,
      clearAuthAndRedirect,
    ],
  )

  return (
    <AdminLayout>
      <section className="admin-bookings">
        <header className="admin-bookings__header">
          <h1 className="admin-bookings__title">Bookings</h1>
          <p className="admin-bookings__lead">
            {manage
              ? 'View bookings and cancel or reschedule pending and confirmed appointments.'
              : 'Read-only list for your salon.'}
          </p>
        </header>

        <form
          className="admin-bookings__filters"
          onSubmit={(event) => {
            event.preventDefault()
            void load()
          }}
        >
          <label className="admin-bookings__filter">
            <span>From</span>
            <input
              type="date"
              value={dateFrom}
              onChange={(event) => setDateFrom(event.target.value)}
            />
          </label>
          <label className="admin-bookings__filter">
            <span>To</span>
            <input
              type="date"
              value={dateTo}
              onChange={(event) => setDateTo(event.target.value)}
            />
          </label>
          <label className="admin-bookings__filter">
            <span>Status</span>
            <select
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option.label} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" className="btn btn--secondary btn--compact">
            Apply
          </button>
        </form>

        {manage && actionMode === 'cancel' && actionBooking ? (
          <form
            className="admin-bookings__form"
            onSubmit={(event) => void handleConfirmCancel(event)}
          >
            <h2 className="admin-bookings__form-title">Cancel booking</h2>
            <p className="admin-bookings__form-lead">
              {actionBooking.customer_name} · {formatDateTime(actionBooking.starts_at)} ·{' '}
              {actionBooking.service_name}
            </p>
            <div className="admin-bookings__form-grid">
              <label className="admin-bookings__filter admin-bookings__filter--wide">
                <span>Reason (optional)</span>
                <input
                  type="text"
                  maxLength={255}
                  value={cancelReason}
                  onChange={(event) => setCancelReason(event.target.value)}
                  placeholder="Optional"
                  disabled={actionSubmitting}
                />
              </label>
            </div>
            <div className="admin-bookings__form-actions">
              <button
                type="submit"
                className="btn btn--primary btn--compact"
                disabled={actionSubmitting}
              >
                Confirm cancel
              </button>
              <button
                type="button"
                className="btn btn--secondary btn--compact"
                onClick={clearAction}
                disabled={actionSubmitting}
              >
                Back
              </button>
            </div>
          </form>
        ) : null}

        {manage && actionMode === 'reschedule' && actionBooking ? (
          <form
            className="admin-bookings__form"
            onSubmit={(event) => void handleConfirmReschedule(event)}
          >
            <h2 className="admin-bookings__form-title">Reschedule booking</h2>
            <p className="admin-bookings__form-lead">
              {actionBooking.customer_name} · {actionBooking.service_name} ·{' '}
              {actionBooking.duration_minutes} min
            </p>
            <div className="admin-bookings__form-grid">
              <label className="admin-bookings__filter">
                <span>Staff</span>
                <select
                  value={rescheduleStaffId}
                  onChange={(event) => setRescheduleStaffId(event.target.value)}
                  disabled={actionSubmitting || staffLoading || staffList.length === 0}
                  required
                >
                  {staffList.length === 0 ? (
                    <option value="">No bookable staff</option>
                  ) : null}
                  {staffList.map((staff) => (
                    <option key={staff.id} value={staff.id}>
                      {staff.display_name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="admin-bookings__filter">
                <span>Service start</span>
                <input
                  type="datetime-local"
                  required
                  value={rescheduleStartLocal}
                  onChange={(event) => setRescheduleStartLocal(event.target.value)}
                  disabled={actionSubmitting}
                />
              </label>
            </div>
            <div className="admin-bookings__form-actions">
              <button
                type="submit"
                className="btn btn--primary btn--compact"
                disabled={
                  actionSubmitting || staffLoading || staffList.length === 0
                }
              >
                Confirm reschedule
              </button>
              <button
                type="button"
                className="btn btn--secondary btn--compact"
                onClick={clearAction}
                disabled={actionSubmitting}
              >
                Back
              </button>
            </div>
          </form>
        ) : null}

        {actionError ? (
          <p className="admin-bookings__state admin-bookings__state--error" role="alert">
            {actionError}
          </p>
        ) : null}

        {loading ? (
          <p className="admin-bookings__state" role="status">
            Loading bookings…
          </p>
        ) : null}

        {!loading && error ? (
          <p className="admin-bookings__state admin-bookings__state--error" role="alert">
            {error}
          </p>
        ) : null}

        {!loading && !error && items.length === 0 ? (
          <p className="admin-bookings__state">No bookings match your filters.</p>
        ) : null}

        {!loading && !error && items.length > 0 ? (
          <div className="admin-bookings__table-wrap">
            <table className="admin-bookings__table">
              <thead>
                <tr>
                  <th scope="col">When</th>
                  <th scope="col">Customer</th>
                  <th scope="col">Service</th>
                  <th scope="col">Staff</th>
                  <th scope="col">Status</th>
                  <th scope="col">Price</th>
                  {manage ? <th scope="col">Actions</th> : null}
                </tr>
              </thead>
              <tbody>
                {items.map((row) => {
                  const actionable = isActionableBookingStatus(row.status)
                  const isActiveRow = actionBooking?.id === row.id
                  return (
                    <tr key={row.id}>
                      <td>{formatDateTime(row.starts_at)}</td>
                      <td>
                        <span className="admin-bookings__customer-name">{row.customer_name}</span>
                        {row.customer_phone ? (
                          <span className="admin-bookings__customer-phone">{row.customer_phone}</span>
                        ) : null}
                      </td>
                      <td>{row.service_name}</td>
                      <td>{row.staff_name}</td>
                      <td>
                        <span className="admin-bookings__status">{row.status.replace('_', ' ')}</span>
                      </td>
                      <td>{formatPrice(row.price_cents)}</td>
                      {manage ? (
                        <td className="admin-bookings__actions">
                          {actionable ? (
                            <>
                              <button
                                type="button"
                                className="btn btn--secondary btn--compact"
                                onClick={() => startReschedule(row)}
                                disabled={
                                  actionSubmitting ||
                                  (isActiveRow && actionMode === 'reschedule')
                                }
                              >
                                Reschedule
                              </button>
                              <button
                                type="button"
                                className="btn btn--secondary btn--compact"
                                onClick={() => startCancel(row)}
                                disabled={
                                  actionSubmitting ||
                                  (isActiveRow && actionMode === 'cancel')
                                }
                              >
                                Cancel
                              </button>
                            </>
                          ) : (
                            <span className="admin-bookings__actions-muted">—</span>
                          )}
                        </td>
                      ) : null}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </AdminLayout>
  )
}
