import { useCallback, useEffect, useState } from 'react'
import { AdminLayout } from '../components/AdminLayout'
import { useAuth } from '../auth/AuthContext'
import { fetchAdminStaff } from '../api/staff'
import { ApiError } from '../api/errors'
import { isUnauthorizedError } from '../api/auth'
import type { StaffListItem } from '../types/staff'

function formatBool(value: boolean): string {
  return value ? 'Yes' : 'No'
}

export function AdminStaffPage() {
  const { session, clearAuthAndRedirect } = useAuth()
  const [items, setItems] = useState<StaffListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showInactive, setShowInactive] = useState(false)

  const load = useCallback(async () => {
    if (!session) {
      return
    }
    setLoading(true)
    setError(null)
    try {
      const rows = await fetchAdminStaff(session.token, session.salon.salon_id, {
        active_only: showInactive ? false : undefined,
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
        setError('Could not load staff.')
      }
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [session, showInactive, clearAuthAndRedirect])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <AdminLayout>
      <section className="admin-staff">
        <header className="admin-staff__header">
          <h1 className="admin-staff__title">Staff</h1>
          <p className="admin-staff__lead">Read-only list for your salon.</p>
        </header>

        <div className="admin-staff__filters">
          <label className="admin-staff__filter admin-staff__filter--checkbox">
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(event) => setShowInactive(event.target.checked)}
            />
            <span>Show inactive</span>
          </label>
        </div>

        {loading ? (
          <p className="admin-staff__state" role="status">
            Loading staff…
          </p>
        ) : null}

        {!loading && error ? (
          <p className="admin-staff__state admin-staff__state--error" role="alert">
            {error}
          </p>
        ) : null}

        {!loading && !error && items.length === 0 ? (
          <p className="admin-staff__state">No staff match your filters.</p>
        ) : null}

        {!loading && !error && items.length > 0 ? (
          <div className="admin-staff__table-wrap">
            <table className="admin-staff__table">
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Title</th>
                  <th scope="col">Active</th>
                  <th scope="col">Bookable</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <span className="admin-staff__name">{row.display_name}</span>
                    </td>
                    <td>{row.title ?? '—'}</td>
                    <td>{formatBool(row.is_active)}</td>
                    <td>{formatBool(row.is_bookable)}</td>
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
