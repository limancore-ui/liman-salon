import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { AdminLayout } from '../components/AdminLayout'
import { useAuth } from '../auth/AuthContext'
import {
  createAdminService,
  fetchAdminServices,
  patchAdminService,
} from '../api/services'
import { ApiError } from '../api/errors'
import { isUnauthorizedError } from '../api/auth'
import { AdminEntityMediaAttach } from '../components/AdminEntityMediaAttach'
import { useSalonMediaAttachmentIndex } from '../hooks/useSalonMediaAttachmentIndex'
import type { ServiceListItem } from '../types/services'
import { formatDuration, formatPrice } from '../utils/format'
import {
  buildServiceUpdatePatch,
  serviceFormFromRow,
  type ParsedServiceFormValues,
  type ServiceFormState,
} from '../utils/adminServiceForm'

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

function mapAdminServiceEditError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 403) {
      return 'You do not have permission to update services.'
    }
    if (err.status === 422 && err.message.trim() !== '') {
      return err.message
    }
    if (err.status === 0) {
      return 'Could not reach the server. Check your connection and try again.'
    }
    return 'Could not update the service. Try again later.'
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

const emptyCreateForm = (): ServiceFormState => ({
  name: '',
  description: '',
  durationMinutes: '30',
  priceMajor: '0',
  bufferBefore: '0',
  bufferAfter: '0',
  sortOrder: '0',
})

function parseServiceFormFields(form: ServiceFormState): ParsedServiceFormValues | string {
  const name = form.name.trim()
  if (name === '') {
    return 'Name is required.'
  }

  const durationMinutes = parseDurationMinutes(form.durationMinutes)
  if (durationMinutes === null) {
    return 'Duration must be a positive whole number of minutes.'
  }

  const bufferBefore = parseNonNegativeInt(form.bufferBefore)
  if (bufferBefore === null) {
    return 'Buffer before must be a non-negative whole number of minutes.'
  }

  const bufferAfter = parseNonNegativeInt(form.bufferAfter)
  if (bufferAfter === null) {
    return 'Buffer after must be a non-negative whole number of minutes.'
  }

  const sortOrder = parseNonNegativeInt(form.sortOrder)
  if (sortOrder === null) {
    return 'Sort order must be a non-negative whole number.'
  }

  const priceCents = parsePriceCents(form.priceMajor)
  if (priceCents === null) {
    return 'Price must be a non-negative number.'
  }

  const descriptionTrimmed = form.description.trim()

  return {
    name,
    description: descriptionTrimmed === '' ? null : descriptionTrimmed,
    duration_minutes: durationMinutes,
    price_cents: priceCents,
    buffer_before_minutes: bufferBefore,
    buffer_after_minutes: bufferAfter,
    sort_order: sortOrder,
  }
}

function ServiceFormFields({
  form,
  onChange,
  currencyCode,
  disabled,
}: {
  form: ServiceFormState
  onChange: (updater: (prev: ServiceFormState) => ServiceFormState) => void
  currencyCode: string
  disabled: boolean
}) {
  return (
    <div className="admin-services__form-grid">
      <label className="admin-services__filter admin-services__filter--wide">
        <span>Name</span>
        <input
          type="text"
          value={form.name}
          onChange={(event) =>
            onChange((prev) => ({ ...prev, name: event.target.value }))
          }
          maxLength={200}
          required
          autoComplete="off"
          disabled={disabled}
        />
      </label>
      <label className="admin-services__filter admin-services__filter--wide">
        <span>Description</span>
        <textarea
          value={form.description}
          onChange={(event) =>
            onChange((prev) => ({
              ...prev,
              description: event.target.value,
            }))
          }
          rows={3}
          disabled={disabled}
        />
      </label>
      <label className="admin-services__filter">
        <span>Duration (minutes)</span>
        <input
          type="number"
          min={1}
          step={1}
          value={form.durationMinutes}
          onChange={(event) =>
            onChange((prev) => ({
              ...prev,
              durationMinutes: event.target.value,
            }))
          }
          disabled={disabled}
        />
      </label>
      <label className="admin-services__filter">
        <span>Price ({currencyCode})</span>
        <input
          type="number"
          min={0}
          step={0.01}
          value={form.priceMajor}
          onChange={(event) =>
            onChange((prev) => ({
              ...prev,
              priceMajor: event.target.value,
            }))
          }
          disabled={disabled}
        />
      </label>
      <label className="admin-services__filter">
        <span>Buffer before (minutes)</span>
        <input
          type="number"
          min={0}
          step={1}
          value={form.bufferBefore}
          onChange={(event) =>
            onChange((prev) => ({
              ...prev,
              bufferBefore: event.target.value,
            }))
          }
          disabled={disabled}
        />
      </label>
      <label className="admin-services__filter">
        <span>Buffer after (minutes)</span>
        <input
          type="number"
          min={0}
          step={1}
          value={form.bufferAfter}
          onChange={(event) =>
            onChange((prev) => ({
              ...prev,
              bufferAfter: event.target.value,
            }))
          }
          disabled={disabled}
        />
      </label>
      <label className="admin-services__filter">
        <span>Sort order</span>
        <input
          type="number"
          min={0}
          step={1}
          value={form.sortOrder}
          onChange={(event) =>
            onChange((prev) => ({
              ...prev,
              sortOrder: event.target.value,
            }))
          }
          disabled={disabled}
        />
      </label>
    </div>
  )
}

export function AdminServicesPage() {
  const { session, clearAuthAndRedirect } = useAuth()
  const [items, setItems] = useState<ServiceListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showInactive, setShowInactive] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [createForm, setCreateForm] = useState<ServiceFormState>(emptyCreateForm)
  const [createSubmitting, setCreateSubmitting] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<ServiceFormState>(emptyCreateForm)
  const [editSubmitting, setEditSubmitting] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)

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
    setEditingId(null)
    setEditForm(emptyCreateForm())
    setEditError(null)
    setEditSubmitting(false)
    setCreateOpen(true)
    setCreateForm(emptyCreateForm())
    setCreateError(null)
  }, [])

  const clearEdit = useCallback(() => {
    setEditingId(null)
    setEditForm(emptyCreateForm())
    setEditError(null)
    setEditSubmitting(false)
  }, [])

  const startEdit = useCallback((row: ServiceListItem) => {
    setCreateOpen(false)
    setCreateForm(emptyCreateForm())
    setCreateError(null)
    setCreateSubmitting(false)
    setEditingId(row.id)
    setEditForm(serviceFormFromRow(row))
    setEditError(null)
  }, [])

  const handleCreateSubmit = useCallback(
    async (event: FormEvent) => {
      event.preventDefault()
      if (!session || !canWrite || !createOpen || createSubmitting) {
        return
      }

      const parsed = parseServiceFormFields(createForm)
      if (typeof parsed === 'string') {
        setCreateError(parsed)
        return
      }

      setCreateSubmitting(true)
      setCreateError(null)
      try {
        await createAdminService(session.token, session.salon.salon_id, {
          name: parsed.name,
          description: parsed.description,
          duration_minutes: parsed.duration_minutes,
          buffer_before_minutes: parsed.buffer_before_minutes,
          buffer_after_minutes: parsed.buffer_after_minutes,
          price_cents: parsed.price_cents,
          sort_order: parsed.sort_order,
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

  const handleEditSubmit = useCallback(
    async (event: FormEvent) => {
      event.preventDefault()
      if (!session || !canWrite || editingId === null || editSubmitting) {
        return
      }

      const original = items.find((row) => row.id === editingId)
      if (!original) {
        setEditError('This service is no longer in the list. Refresh and try again.')
        return
      }

      const parsed = parseServiceFormFields(editForm)
      if (typeof parsed === 'string') {
        setEditError(parsed)
        return
      }

      const patchBody = buildServiceUpdatePatch(original, parsed)
      if (Object.keys(patchBody).length === 0) {
        clearEdit()
        return
      }

      setEditSubmitting(true)
      setEditError(null)
      try {
        await patchAdminService(
          session.token,
          session.salon.salon_id,
          editingId,
          patchBody,
        )
        clearEdit()
        await load()
      } catch (err) {
        if (isUnauthorizedError(err)) {
          clearAuthAndRedirect()
          return
        }
        setEditError(mapAdminServiceEditError(err))
      } finally {
        setEditSubmitting(false)
      }
    },
    [
      session,
      canWrite,
      editingId,
      editSubmitting,
      items,
      editForm,
      clearEdit,
      load,
      clearAuthAndRedirect,
    ],
  )

  const editingRow =
    editingId !== null ? items.find((row) => row.id === editingId) : undefined

  return (
    <AdminLayout>
      <section className="admin-services">
        <header className="admin-services__header">
          <h1 className="admin-services__title">Services</h1>
          <p className="admin-services__lead">
            Service catalog for your salon. Owners and admins can add services and set
            cover images from the media library.
          </p>
          {canWrite && !createOpen && editingId === null ? (
            <p className="admin-services__header-actions">
              <button
                type="button"
                className="btn btn--primary btn--compact"
                onClick={startCreate}
                disabled={createSubmitting || editSubmitting}
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
            <ServiceFormFields
              form={createForm}
              onChange={setCreateForm}
              currencyCode={currencyCode}
              disabled={createSubmitting}
            />
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

        {canWrite && editingId !== null ? (
          <form
            className="admin-services__form"
            onSubmit={(event) => void handleEditSubmit(event)}
          >
            <h2 className="admin-services__form-title">
              Edit service{editingRow ? `: ${editingRow.name}` : ''}
            </h2>
            <p className="admin-services__form-lead">
              Only changed fields are sent to the server. Price is in {currencyCode}{' '}
              (major units, e.g. 25.00).
            </p>
            {editError ? (
              <p className="admin-services__form-error" role="alert">
                {editError}
              </p>
            ) : null}
            <ServiceFormFields
              form={editForm}
              onChange={setEditForm}
              currencyCode={currencyCode}
              disabled={editSubmitting}
            />
            <div className="admin-services__form-actions">
              <button
                type="submit"
                className="btn btn--primary btn--compact"
                disabled={editSubmitting}
              >
                {editSubmitting ? 'Saving…' : 'Save changes'}
              </button>
              <button
                type="button"
                className="btn btn--secondary btn--compact"
                onClick={clearEdit}
                disabled={editSubmitting}
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
                  {canWrite ? <th scope="col">Actions</th> : null}
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
                    {canWrite ? (
                      <td>
                        <button
                          type="button"
                          className="btn btn--secondary btn--compact"
                          onClick={() => startEdit(row)}
                          disabled={
                            createSubmitting ||
                            editSubmitting ||
                            (editingId !== null && editingId !== row.id)
                          }
                        >
                          Edit
                        </button>
                      </td>
                    ) : null}
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
