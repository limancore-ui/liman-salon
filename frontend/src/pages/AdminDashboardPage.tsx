import { useCallback, useEffect, useMemo, useState } from 'react'
import { AdminLayout } from '../components/AdminLayout'
import { useAuth } from '../auth/AuthContext'
import { fetchAdminDashboard } from '../api/dashboard'
import { ApiError } from '../api/errors'
import { isUnauthorizedError } from '../api/auth'
import type {
  AdminDashboardSnapshot,
  DashboardStatusCounts,
  DashboardWarning,
} from '../types/dashboard'
import {
  formatBookingTime,
  formatDashboardPrice,
} from '../utils/adminSalonFormat'

const STATUS_SUMMARY: {
  key: keyof DashboardStatusCounts
  label: string
}[] = [
  { key: 'pending', label: 'Pending' },
  { key: 'confirmed', label: 'Confirmed' },
  { key: 'in_progress', label: 'In progress' },
  { key: 'completed', label: 'Completed' },
  { key: 'cancelled', label: 'Cancelled' },
  { key: 'no_show', label: 'No show' },
  { key: 'expired', label: 'Expired' },
]

const KNOWN_WARNING_MESSAGES: Record<string, string> = {
  no_active_staff: 'No active staff members for this salon.',
  no_bookable_staff: 'No bookable staff available for new bookings.',
}

const SESSION_GAP_MESSAGES = {
  timezone:
    'Salon timezone is not available on the authenticated session (GET /auth/salons/{salon_id}/context). Booking times cannot be shown in salon local time until the auth context exposes timezone.',
  currency:
    'Salon currency is not available on the authenticated session (GET /auth/salons/{salon_id}/context). Prices are shown as major units without a currency code until the auth context exposes currency_code.',
} as const

function formatSalonDate(isoDate: string, timeZone: string | undefined): string {
  const [year, month, day] = isoDate.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1, day, 12, 0, 0))
  return date.toLocaleDateString(undefined, {
    dateStyle: 'full',
    ...(timeZone ? { timeZone } : {}),
  })
}

function formatStatusLabel(status: string): string {
  return status.replaceAll('_', ' ')
}

function formatWarningMessage(warning: DashboardWarning): string {
  const known = KNOWN_WARNING_MESSAGES[warning.code]
  if (known) {
    if (warning.count != null) {
      return `${known} (${warning.count})`
    }
    return known
  }
  const label = warning.code.replaceAll('_', ' ')
  if (warning.count != null) {
    return `${label} (${warning.count})`
  }
  return label
}

function isDashboardEmpty(snapshot: AdminDashboardSnapshot): boolean {
  return (
    snapshot.today_booking_count === 0 &&
    snapshot.upcoming_bookings.length === 0 &&
    snapshot.status_counts.pending === 0 &&
    snapshot.status_counts.confirmed === 0 &&
    snapshot.status_counts.in_progress === 0 &&
    snapshot.status_counts.completed === 0 &&
    snapshot.status_counts.cancelled === 0 &&
    snapshot.status_counts.no_show === 0 &&
    snapshot.status_counts.expired === 0
  )
}

export function AdminDashboardPage() {
  const { session, clearAuthAndRedirect } = useAuth()
  const [snapshot, setSnapshot] = useState<AdminDashboardSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const salonTimeZone = session?.salon.timezone
  const salonCurrencyCode = session?.salon.currency_code ?? undefined

  const sessionGaps = useMemo(() => {
    const gaps: string[] = []
    if (!salonTimeZone) {
      gaps.push(SESSION_GAP_MESSAGES.timezone)
    }
    if (!salonCurrencyCode) {
      gaps.push(SESSION_GAP_MESSAGES.currency)
    }
    return gaps
  }, [salonTimeZone, salonCurrencyCode])

  const load = useCallback(async () => {
    if (!session) {
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await fetchAdminDashboard(session.token, session.salon.salon_id)
      setSnapshot(data)
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError('Could not load dashboard.')
      }
      setSnapshot(null)
    } finally {
      setLoading(false)
    }
  }, [session, clearAuthAndRedirect])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <AdminLayout>
      <section className="admin-dashboard">
        <header className="admin-dashboard__header">
          <h1 className="admin-dashboard__title">Dashboard</h1>
          {snapshot ? (
            <p className="admin-dashboard__date">
              Salon date:{' '}
              <time dateTime={snapshot.salon_date}>
                {formatSalonDate(snapshot.salon_date, salonTimeZone)}
              </time>
            </p>
          ) : (
            <p className="admin-dashboard__date admin-dashboard__date--muted">
              Operational overview for your salon
            </p>
          )}
        </header>

        {loading ? (
          <p className="admin-dashboard__state" role="status">
            Loading dashboard…
          </p>
        ) : null}

        {!loading && error ? (
          <p className="admin-dashboard__state admin-dashboard__state--error" role="alert">
            {error}
          </p>
        ) : null}

        {!loading && !error && snapshot ? (
          <>
            {sessionGaps.length > 0 ? (
              <ul className="admin-dashboard__warnings" aria-label="Session context gaps">
                {sessionGaps.map((message) => (
                  <li key={message} className="admin-dashboard__warning">
                    {message}
                  </li>
                ))}
              </ul>
            ) : null}

            {snapshot.warnings.length > 0 ? (
              <ul className="admin-dashboard__warnings" aria-label="Dashboard warnings">
                {snapshot.warnings.map((warning) => (
                  <li key={warning.code} className="admin-dashboard__warning">
                    {formatWarningMessage(warning)}
                  </li>
                ))}
              </ul>
            ) : null}

            {isDashboardEmpty(snapshot) ? (
              <p className="admin-dashboard__state">No booking activity for today yet.</p>
            ) : null}

            <div className="admin-dashboard__summary">
              <div className="admin-dashboard__stat">
                <span className="admin-dashboard__stat-label">Today&apos;s bookings</span>
                <span className="admin-dashboard__stat-value">{snapshot.today_booking_count}</span>
              </div>
              <div className="admin-dashboard__stat">
                <span className="admin-dashboard__stat-label">Active staff</span>
                <span className="admin-dashboard__stat-value">{snapshot.active_staff_count}</span>
              </div>
            </div>

            <section className="admin-dashboard__panel" aria-labelledby="dashboard-status-heading">
              <h2 id="dashboard-status-heading" className="admin-dashboard__panel-title">
                Booking status today
              </h2>
              <dl className="admin-dashboard__status-grid">
                {STATUS_SUMMARY.map(({ key, label }) => (
                  <div key={key} className="admin-dashboard__status-item">
                    <dt>{label}</dt>
                    <dd aria-label={`${label} count`}>{snapshot.status_counts[key]}</dd>
                  </div>
                ))}
              </dl>
            </section>

            <section className="admin-dashboard__panel" aria-labelledby="dashboard-upcoming-heading">
              <h2 id="dashboard-upcoming-heading" className="admin-dashboard__panel-title">
                Upcoming bookings today
              </h2>

              {snapshot.upcoming_bookings.length === 0 ? (
                <p className="admin-dashboard__empty">No upcoming bookings for today.</p>
              ) : (
                <div className="admin-bookings__table-wrap">
                  <table className="admin-bookings__table">
                    <thead>
                      <tr>
                        <th scope="col">Time</th>
                        <th scope="col">Customer</th>
                        <th scope="col">Service</th>
                        <th scope="col">Staff</th>
                        <th scope="col">Status</th>
                        <th scope="col">Price</th>
                      </tr>
                    </thead>
                    <tbody>
                      {snapshot.upcoming_bookings.map((row) => (
                        <tr key={row.id}>
                          <td>{formatBookingTime(row.starts_at, salonTimeZone)}</td>
                          <td>
                            <span className="admin-bookings__customer-name">{row.customer_name}</span>
                            {row.customer_phone ? (
                              <span className="admin-bookings__customer-phone">{row.customer_phone}</span>
                            ) : null}
                          </td>
                          <td>{row.service_name}</td>
                          <td>{row.staff_name}</td>
                          <td>
                            <span className="admin-bookings__status">{formatStatusLabel(row.status)}</span>
                          </td>
                          <td>{formatDashboardPrice(row.price_cents, salonCurrencyCode)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </>
        ) : null}
      </section>
    </AdminLayout>
  )
}
