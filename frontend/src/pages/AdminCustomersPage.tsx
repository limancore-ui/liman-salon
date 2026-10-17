import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { AdminLayout } from '../components/AdminLayout'
import { useAuth } from '../auth/AuthContext'
import { fetchAdminCustomers } from '../api/customers'
import { isUnauthorizedError } from '../api/auth'
import { adminUserErrorMessage } from '../utils/adminUserError'
import type { CustomerListItem } from '../types/customers'
import { formatDashboardPrice } from '../utils/adminSalonFormat'
import { t } from '../i18n'

function formatBool(value: boolean): string {
  return value ? t('common.yes') : t('common.no')
}

export function AdminCustomersPage() {
  const { session, clearAuthAndRedirect } = useAuth()
  const salonCurrencyCode = session?.salon.currency_code ?? undefined
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
      setError(adminUserErrorMessage(err, 'admin.customers.loadFailed'))
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
          <h1 className="admin-customers__title">{t('admin.customers.title')}</h1>
          <p className="admin-customers__lead">{t('admin.customers.lead')}</p>
        </header>

        <form className="admin-customers__filters" onSubmit={handleSearchSubmit}>
          <label className="admin-customers__filter">
            <span>{t('common.search')}</span>
            <input
              type="search"
              className="admin-customers__search-input"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder={t('admin.customers.searchPlaceholder')}
              autoComplete="off"
            />
          </label>
          <button type="submit" className="btn btn--secondary btn--compact">
            Apply
          </button>
        </form>

        {loading ? (
          <p className="admin-customers__state" role="status">
            {t('admin.customers.loading')}
          </p>
        ) : null}

        {!loading && error ? (
          <p className="admin-customers__state admin-customers__state--error" role="alert">
            {error}
          </p>
        ) : null}

        {!loading && !error && items.length === 0 ? (
          <p className="admin-customers__state">{t('admin.customers.empty')}</p>
        ) : null}

        {!loading && !error && items.length > 0 ? (
          <div className="admin-customers__table-wrap">
            <table className="admin-customers__table">
              <thead>
                <tr>
                  <th scope="col">{t('admin.customers.colName')}</th>
                  <th scope="col">{t('admin.customers.colPhone')}</th>
                  <th scope="col">{t('admin.customers.colEmail')}</th>
                  <th scope="col">{t('admin.customers.colBonus')}</th>
                  <th scope="col">{t('admin.customers.colWhatsApp')}</th>
                  <th scope="col">{t('admin.customers.colMarketing')}</th>
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
                    <td>{formatDashboardPrice(row.bonus_balance_cents, salonCurrencyCode)}</td>
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
