import { useCallback, useEffect, useState } from 'react'
import { AdminLayout } from '../components/AdminLayout'
import { useAuth } from '../auth/AuthContext'
import { fetchAdminBookings } from '../api/bookings'
import { ApiError } from '../api/errors'
import { isUnauthorizedError } from '../api/auth'
import type { BookingListItem } from '../types/bookings'

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

export function AdminBookingsPage() {
  const { session, clearAuthAndRedirect } = useAuth()
  const [items, setItems] = useState<BookingListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [status, setStatus] = useState('')

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

  return (
    <AdminLayout>
      <section className="admin-bookings">
        <header className="admin-bookings__header">
          <h1 className="admin-bookings__title">Bookings</h1>
          <p className="admin-bookings__lead">Read-only list for your salon.</p>
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
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
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
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </AdminLayout>
  )
}
