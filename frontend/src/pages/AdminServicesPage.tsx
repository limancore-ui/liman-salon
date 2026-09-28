import { useCallback, useEffect, useState } from 'react'
import { AdminLayout } from '../components/AdminLayout'
import { useAuth } from '../auth/AuthContext'
import { fetchAdminServices } from '../api/services'
import { ApiError } from '../api/errors'
import { isUnauthorizedError } from '../api/auth'
import { AdminEntityMediaAttach } from '../components/AdminEntityMediaAttach'
import { useSalonMediaAttachmentIndex } from '../hooks/useSalonMediaAttachmentIndex'
import type { ServiceListItem } from '../types/services'
import { formatDuration, formatPrice } from '../utils/format'

function canManageMedia(role: string | undefined): boolean {
  return role === 'owner' || role === 'admin'
}

function formatBool(value: boolean): string {
  return value ? 'Yes' : 'No'
}

function servicePrice(row: ServiceListItem): string {
  return formatPrice(row.price_cents, row.currency_code ?? 'USD')
}

export function AdminServicesPage() {
  const { session, clearAuthAndRedirect } = useAuth()
  const [items, setItems] = useState<ServiceListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showInactive, setShowInactive] = useState(false)

  const canWrite = canManageMedia(session?.salon.role)
  const mediaIndex = useSalonMediaAttachmentIndex(
    session?.token,
    session?.salon.salon_id,
    clearAuthAndRedirect,
  )

  const load = useCallback(async () => {
    if (!session) {
      return
    }
    setLoading(true)
    setError(null)
    try {
      const rows = await fetchAdminServices(session.token, session.salon.salon_id, {
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
        setError('Could not load services.')
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
      <section className="admin-services">
        <header className="admin-services__header">
          <h1 className="admin-services__title">Services</h1>
          <p className="admin-services__lead">
            Service catalog for your salon. Owners and admins can set cover images from
            the media library.
          </p>
        </header>

        {mediaIndex.error ? (
          <p className="admin-services__state admin-services__state--error" role="alert">
            {mediaIndex.error}
          </p>
        ) : null}

        <div className="admin-services__filters">
          <label className="admin-services__filter admin-services__filter--checkbox">
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(event) => setShowInactive(event.target.checked)}
            />
            <span>Show inactive</span>
          </label>
        </div>

        {loading ? (
          <p className="admin-services__state" role="status">
            Loading services…
          </p>
        ) : null}

        {!loading && error ? (
          <p className="admin-services__state admin-services__state--error" role="alert">
            {error}
          </p>
        ) : null}

        {!loading && !error && items.length === 0 ? (
          <p className="admin-services__state">No services match your filters.</p>
        ) : null}

        {!loading && !error && items.length > 0 ? (
          <div className="admin-services__table-wrap">
            <table className="admin-services__table">
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Description</th>
                  <th scope="col">Duration</th>
                  <th scope="col">Price</th>
                  <th scope="col">Active</th>
                  <th scope="col">Cover</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <span className="admin-services__name">{row.name}</span>
                    </td>
                    <td>{row.description ?? '—'}</td>
                    <td>{formatDuration(row.duration_minutes)}</td>
                    <td>{servicePrice(row)}</td>
                    <td>{formatBool(row.is_active)}</td>
                    <td>
                      {session ? (
                        <AdminEntityMediaAttach
                          token={session.token}
                          salonId={session.salon.salon_id}
                          canWrite={canWrite}
                          entityType="service"
                          entityId={row.id}
                          purpose="cover"
                          label="Cover"
                          assets={mediaIndex.assets}
                          attachment={mediaIndex.getAttachment(
                            'service',
                            row.id,
                            'cover',
                          )}
                          attachmentLoading={mediaIndex.loading}
                          onUpdated={mediaIndex.reload}
                          onUnauthorized={clearAuthAndRedirect}
                          compact
                        />
                      ) : null}
                    </td>
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
