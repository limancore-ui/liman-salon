import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { AdminLayout } from '../components/AdminLayout'
import { useAuth } from '../auth/AuthContext'
import { fetchAdminCustomers } from '../api/customers'
import { ApiError } from '../api/errors'
import { isUnauthorizedError } from '../api/auth'
import type { CustomerListItem } from '../types/customers'
import { formatPrice } from '../utils/format'

function formatBool(value: boolean): string {
  return value ? 'Yes' : 'No'
}

function bonusBalance(row: CustomerListItem): string {
  return formatPrice(row.bonus_balance_cents, 'USD')
}

export function AdminCustomersPage() {
  const { session, clearAuthAndRedirect } = useAuth()
  const [items, setItems] = useState<CustomerListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchInput, setSearchInput] = useState('')
  const [appliedQ, setAppliedQ] = useState<string | undefined>(undefined)

  const load = useCallback(async () => {
    if (!session) {
      return
    }
    setLoading(true)
    setError(null)
    try {
      const rows = await fetchAdminCustomers(session.token, session.salon.salon_id, {
        q: appliedQ,
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
        setError('Could not load customers.')
      }
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [session, appliedQ, clearAuthAndRedirect])

  useEffect(() => {
    void load()
  }, [load])

  function handleSearchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmed = searchInput.trim()
    setAppliedQ(trimmed === '' ? undefined : trimmed)
  }

  return (
    <AdminLayout>
      <section className="admin-customers">
        <header className="admin-customers__header">
          <h1 className="admin-customers__title">Customers</h1>
          <p className="admin-customers__lead">Read-only list for your salon.</p>
        </header>

        <form className="admin-customers__filters" onSubmit={handleSearchSubmit}>
          <label className="admin-customers__filter">
            <span>Search</span>
            <input
              type="search"
              className="admin-customers__search-input"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Name, phone, or email"
              autoComplete="off"
            />
          </label>
          <button type="submit" className="btn btn--secondary btn--compact">
            Apply
          </button>
        </form>

        {loading ? (
          <p className="admin-customers__state" role="status">
            Loading customers…
          </p>
        ) : null}

        {!loading && error ? (
          <p className="admin-customers__state admin-customers__state--error" role="alert">
            {error}
          </p>
        ) : null}

        {!loading && !error && items.length === 0 ? (
          <p className="admin-customers__state">No customers match your search.</p>
        ) : null}

        {!loading && !error && items.length > 0 ? (
          <div className="admin-customers__table-wrap">
            <table className="admin-customers__table">
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Phone</th>
                  <th scope="col">Email</th>
                  <th scope="col">Bonus</th>
                  <th scope="col">WhatsApp</th>
                  <th scope="col">Marketing</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <span className="admin-customers__name">{row.full_name}</span>
                    </td>
                    <td>{row.phone ?? '—'}</td>
                    <td>{row.email ?? '—'}</td>
                    <td>{bonusBalance(row)}</td>
                    <td>{formatBool(row.whatsapp_opt_in)}</td>
                    <td>{formatBool(row.marketing_opt_in)}</td>
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
