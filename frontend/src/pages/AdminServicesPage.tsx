import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { AdminLayout } from '../components/AdminLayout'
import { useAuth } from '../auth/AuthContext'
import { createAdminService, fetchAdminServices } from '../api/services'
import { ApiError } from '../api/errors'
import { isUnauthorizedError } from '../api/auth'
import { AdminEntityMediaAttach } from '../components/AdminEntityMediaAttach'
import { useSalonMediaAttachmentIndex } from '../hooks/useSalonMediaAttachmentIndex'
import type { ServiceListItem } from '../types/services'
import { formatDuration, formatPrice } from '../utils/format'

function canManageServices(role: string | undefined): boolean {
  return role === 'owner' || role === 'admin'
}

function formatBool(value: boolean): string {
  return value ? 'Yes' : 'No'
}

function servicePrice(row: ServiceListItem): string {
  return formatPrice(row.price_cents, row.currency_code ?? 'USD')
}

function mapAdminServiceCreateError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 403) {
      return 'You do not have permission to create services.'
    }
    if (err.status === 422 && err.message.trim() !== '') {
      return err.message
    }
    if (err.status === 0) {
      return 'Could not reach the server. Check your connection and try again.'
    }
    return 'Could not create the service. Try again later.'
  }
  return 'Could not reach the server. Check your connection and try again.'
}

function parseNonNegativeInt(raw: string): number | null {
  const trimmed = raw.trim()
  if (trimmed === '') {
    return 0
  }
  const parsed = Number(trimmed)
  if (!Number.isInteger(parsed) || parsed < 0) {
    return null
  }
  return parsed
}

function parseDurationMinutes(raw: string): number | null {
  const trimmed = raw.trim()
  if (trimmed === '') {
    return 30
  }
  const parsed = Number(trimmed)
  if (!Number.isInteger(parsed) || parsed <= 0) {
    return null
  }
  return parsed
}

function parsePriceCents(raw: string): number | null {
  const trimmed = raw.trim()
  if (trimmed === '') {
    return 0
  }
  const parsed = Number(trimmed)
  if (!Number.isFinite(parsed) || parsed < 0) {
    return null
  }
  return Math.round(parsed * 100)
}

type CreateFormState = {
  name: string
  description: string
  durationMinutes: string
  priceMajor: string
  bufferBefore: string
  bufferAfter: string
  sortOrder: string
}

const emptyCreateForm = (): CreateFormState => ({
  name: '',
  description: '',
  durationMinutes: '30',
  priceMajor: '0',
  bufferBefore: '0',
  bufferAfter: '0',
  sortOrder: '0',
})

export function AdminServicesPage() {
  const { session, clearAuthAndRedirect } = useAuth()
  const [items, setItems] = useState<ServiceListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showInactive, setShowInactive] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [createForm, setCreateForm] = useState<CreateFormState>(emptyCreateForm)
  const [createSubmitting, setCreateSubmitting] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const canWrite = canManageServices(session?.salon.role)
  const currencyCode = session?.salon.currency_code ?? 'USD'
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

  const clearCreate = useCallback(() => {
    setCreateOpen(false)
    setCreateForm(emptyCreateForm())
    setCreateError(null)
    setCreateSubmitting(false)
  }, [])

  const startCreate = useCallback(() => {
    setCreateOpen(true)
    setCreateForm(emptyCreateForm())
    setCreateError(null)
  }, [])

  const handleCreateSubmit = useCallback(
    async (event: FormEvent) => {
      event.preventDefault()
      if (!session || !canWrite || !createOpen || createSubmitting) {
        return
      }

      const name = createForm.name.trim()
      if (name === '') {
        setCreateError('Name is required.')
        return
      }

      const durationMinutes = parseDurationMinutes(createForm.durationMinutes)
      if (durationMinutes === null) {
        setCreateError('Duration must be a positive whole number of minutes.')
        return
      }

      const bufferBefore = parseNonNegativeInt(createForm.bufferBefore)
      if (bufferBefore === null) {
        setCreateError('Buffer before must be a non-negative whole number of minutes.')
        return
      }

      const bufferAfter = parseNonNegativeInt(createForm.bufferAfter)
      if (bufferAfter === null) {
        setCreateError('Buffer after must be a non-negative whole number of minutes.')
        return
      }

      const sortOrder = parseNonNegativeInt(createForm.sortOrder)
      if (sortOrder === null) {
        setCreateError('Sort order must be a non-negative whole number.')
        return
      }

      const priceCents = parsePriceCents(createForm.priceMajor)
      if (priceCents === null) {
        setCreateError('Price must be a non-negative number.')
        return
      }

      const descriptionTrimmed = createForm.description.trim()

      setCreateSubmitting(true)
      setCreateError(null)
      try {
        await createAdminService(session.token, session.salon.salon_id, {
          name,
          description: descriptionTrimmed === '' ? null : descriptionTrimmed,
          duration_minutes: durationMinutes,
          buffer_before_minutes: bufferBefore,
          buffer_after_minutes: bufferAfter,
          price_cents: priceCents,
          sort_order: sortOrder,
        })
        clearCreate()
        await load()
      } catch (err) {
        if (isUnauthorizedError(err)) {
          clearAuthAndRedirect()
          return
        }
        setCreateError(mapAdminServiceCreateError(err))
      } finally {
        setCreateSubmitting(false)
      }
    },
    [
      session,
      canWrite,
      createOpen,
      createSubmitting,
      createForm,
      clearCreate,
      load,
      clearAuthAndRedirect,
    ],
  )

  return (
    <AdminLayout>
      <section className="admin-services">
        <header className="admin-services__header">
          <h1 className="admin-services__title">Services</h1>
          <p className="admin-services__lead">
            Service catalog for your salon. Owners and admins can add services and set
            cover images from the media library.
          </p>
          {canWrite && !createOpen ? (
            <p className="admin-services__header-actions">
              <button
                type="button"
                className="btn btn--primary btn--compact"
                onClick={startCreate}
                disabled={createSubmitting}
              >
                Create service
              </button>
            </p>
          ) : null}
        </header>

        {canWrite && createOpen ? (
          <form
            className="admin-services__form"
            onSubmit={(event) => void handleCreateSubmit(event)}
          >
            <h2 className="admin-services__form-title">Create service</h2>
            <p className="admin-services__form-lead">
              New services are active by default. Price is in {currencyCode} (major
              units, e.g. 25.00).
            </p>
            {createError ? (
              <p className="admin-services__form-error" role="alert">
                {createError}
              </p>
            ) : null}
            <div className="admin-services__form-grid">
              <label className="admin-services__filter admin-services__filter--wide">
                <span>Name</span>
                <input
                  type="text"
                  value={createForm.name}
                  onChange={(event) =>
                    setCreateForm((prev) => ({ ...prev, name: event.target.value }))
                  }
                  maxLength={200}
                  required
                  autoComplete="off"
                  disabled={createSubmitting}
                />
              </label>
              <label className="admin-services__filter admin-services__filter--wide">
                <span>Description</span>
                <textarea
                  value={createForm.description}
                  onChange={(event) =>
                    setCreateForm((prev) => ({
                      ...prev,
                      description: event.target.value,
                    }))
                  }
                  rows={3}
                  disabled={createSubmitting}
                />
              </label>
              <label className="admin-services__filter">
                <span>Duration (minutes)</span>
                <input
                  type="number"
                  min={1}
                  step={1}
                  value={createForm.durationMinutes}
                  onChange={(event) =>
                    setCreateForm((prev) => ({
                      ...prev,
                      durationMinutes: event.target.value,
                    }))
                  }
                  disabled={createSubmitting}
                />
              </label>
              <label className="admin-services__filter">
                <span>Price ({currencyCode})</span>
                <input
                  type="number"
                  min={0}
                  step={0.01}
                  value={createForm.priceMajor}
                  onChange={(event) =>
                    setCreateForm((prev) => ({
                      ...prev,
                      priceMajor: event.target.value,
                    }))
                  }
                  disabled={createSubmitting}
                />
              </label>
              <label className="admin-services__filter">
                <span>Buffer before (minutes)</span>
                <input
                  type="number"
                  min={0}
                  step={1}
                  value={createForm.bufferBefore}
                  onChange={(event) =>
                    setCreateForm((prev) => ({
                      ...prev,
                      bufferBefore: event.target.value,
                    }))
                  }
                  disabled={createSubmitting}
                />
              </label>
              <label className="admin-services__filter">
                <span>Buffer after (minutes)</span>
                <input
                  type="number"
                  min={0}
                  step={1}
                  value={createForm.bufferAfter}
                  onChange={(event) =>
                    setCreateForm((prev) => ({
                      ...prev,
                      bufferAfter: event.target.value,
                    }))
                  }
                  disabled={createSubmitting}
                />
              </label>
              <label className="admin-services__filter">
                <span>Sort order</span>
                <input
                  type="number"
                  min={0}
                  step={1}
                  value={createForm.sortOrder}
                  onChange={(event) =>
                    setCreateForm((prev) => ({
                      ...prev,
                      sortOrder: event.target.value,
                    }))
                  }
                  disabled={createSubmitting}
                />
              </label>
            </div>
            <div className="admin-services__form-actions">
              <button
                type="submit"
                className="btn btn--primary btn--compact"
                disabled={createSubmitting}
              >
                {createSubmitting ? 'Creating…' : 'Create service'}
              </button>
              <button
                type="button"
                className="btn btn--secondary btn--compact"
                onClick={clearCreate}
                disabled={createSubmitting}
              >
                Cancel
              </button>
            </div>
          </form>
        ) : null}

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
