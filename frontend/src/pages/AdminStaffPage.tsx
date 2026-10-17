import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { AdminLayout } from '../components/AdminLayout'
import { useAuth } from '../auth/AuthContext'
import { createAdminStaff, fetchAdminStaff, patchAdminStaff } from '../api/staff'
import { isUnauthorizedError } from '../api/auth'
import { adminUserErrorMessage } from '../utils/adminUserError'
import { AdminEntityMediaAttach } from '../components/AdminEntityMediaAttach'
import { useSalonMediaAttachmentIndex } from '../hooks/useSalonMediaAttachmentIndex'
import type { StaffListItem } from '../types/staff'
import {
  buildStaffCreateBody,
  buildStaffUpdatePatch,
  emptyStaffForm,
  hasStaffUnsupportedClear,
  mapAdminStaffCreateError,
  mapAdminStaffUpdateError,
  parseStaffFormFields,
  STAFF_UNSUPPORTED_CLEAR_MESSAGE,
  staffActiveToggleLabel,
  staffActiveTogglePatch,
  staffBookableToggleLabel,
  staffBookableTogglePatch,
  staffFormFromRow,
  type StaffFormState,
} from '../utils/adminStaffForm'
import { t } from '../i18n'

function canManageMedia(role: string | undefined): boolean {
  return role === 'owner' || role === 'admin'
}

function formatBool(value: boolean): string {
  return value ? t('common.yes') : t('common.no')
}

function StaffFormFields({
  form,
  onChange,
  disabled,
  idPrefix,
}: {
  form: StaffFormState
  onChange: (updater: (prev: StaffFormState) => StaffFormState) => void
  disabled: boolean
  idPrefix: string
}) {
  return (
    <div className="admin-staff__form-grid">
      <label
        className="admin-staff__filter admin-staff__filter--wide"
        htmlFor={`${idPrefix}-display-name`}
      >
        <span>{t('admin.form.displayName')}</span>
        <input
          id={`${idPrefix}-display-name`}
          type="text"
          value={form.displayName}
          onChange={(event) =>
            onChange((prev) => ({ ...prev, displayName: event.target.value }))
          }
          maxLength={200}
          required
          autoComplete="name"
          disabled={disabled}
        />
      </label>
      <label
        className="admin-staff__filter admin-staff__filter--wide"
        htmlFor={`${idPrefix}-title`}
      >
        <span>{t('admin.form.title')}</span>
        <input
          id={`${idPrefix}-title`}
          type="text"
          value={form.title}
          onChange={(event) =>
            onChange((prev) => ({ ...prev, title: event.target.value }))
          }
          maxLength={100}
          autoComplete="off"
          disabled={disabled}
        />
      </label>
      <label
        className="admin-staff__filter admin-staff__filter--wide"
        htmlFor={`${idPrefix}-bio`}
      >
        <span>{t('admin.form.bio')}</span>
        <textarea
          id={`${idPrefix}-bio`}
          value={form.bio}
          onChange={(event) =>
            onChange((prev) => ({ ...prev, bio: event.target.value }))
          }
          rows={3}
          disabled={disabled}
        />
      </label>
      <label className="admin-staff__filter" htmlFor={`${idPrefix}-color`}>
        <span>{t('admin.form.colorHex')}</span>
        <input
          id={`${idPrefix}-color`}
          type="text"
          value={form.colorHex}
          onChange={(event) =>
            onChange((prev) => ({ ...prev, colorHex: event.target.value }))
          }
          placeholder="#AABBCC"
          autoComplete="off"
          disabled={disabled}
        />
      </label>
      <label className="admin-staff__filter" htmlFor={`${idPrefix}-sort-order`}>
        <span>{t('admin.form.sortOrder')}</span>
        <input
          id={`${idPrefix}-sort-order`}
          type="number"
          min={0}
          step={1}
          value={form.sortOrder}
          onChange={(event) =>
            onChange((prev) => ({ ...prev, sortOrder: event.target.value }))
          }
          disabled={disabled}
        />
      </label>
      <label className="admin-staff__filter admin-staff__filter--checkbox">
        <input
          id={`${idPrefix}-active`}
          type="checkbox"
          checked={form.isActive}
          onChange={(event) =>
            onChange((prev) => ({ ...prev, isActive: event.target.checked }))
          }
          disabled={disabled}
        />
        <span>{t('admin.form.active')}</span>
      </label>
      <label className="admin-staff__filter admin-staff__filter--checkbox">
        <input
          id={`${idPrefix}-bookable`}
          type="checkbox"
          checked={form.isBookable}
          onChange={(event) =>
            onChange((prev) => ({ ...prev, isBookable: event.target.checked }))
          }
          disabled={disabled}
        />
        <span>{t('admin.form.bookable')}</span>
      </label>
    </div>
  )
}

export function AdminStaffPage() {
  const { session, clearAuthAndRedirect } = useAuth()
  const [items, setItems] = useState<StaffListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showInactive, setShowInactive] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [createForm, setCreateForm] = useState<StaffFormState>(emptyStaffForm)
  const [createSubmitting, setCreateSubmitting] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<StaffFormState>(emptyStaffForm)
  const [editSubmitting, setEditSubmitting] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)
  const [deactivateConfirmId, setDeactivateConfirmId] = useState<string | null>(null)
  const [togglingActiveId, setTogglingActiveId] = useState<string | null>(null)
  const [togglingBookableId, setTogglingBookableId] = useState<string | null>(null)
  const [toggleActiveErrors, setToggleActiveErrors] = useState<Record<string, string>>({})
  const [toggleBookableErrors, setToggleBookableErrors] = useState<Record<string, string>>(
    {},
  )

  const canWrite = canManageMedia(session?.salon.role)
  const formBusy =
    createSubmitting ||
    editSubmitting ||
    togglingActiveId !== null ||
    togglingBookableId !== null ||
    deactivateConfirmId !== null

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
      const rows = await fetchAdminStaff(session.token, session.salon.salon_id, {
        active_only: showInactive ? false : undefined,
      })
      setItems(rows)
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      setError(adminUserErrorMessage(err, 'admin.staff.loadFailed'))
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
    setCreateForm(emptyStaffForm())
    setCreateError(null)
    setCreateSubmitting(false)
  }, [])

  const startCreate = useCallback(() => {
    setEditingId(null)
    setEditForm(emptyStaffForm())
    setEditError(null)
    setEditSubmitting(false)
    setCreateOpen(true)
    setCreateForm(emptyStaffForm())
    setCreateError(null)
  }, [])

  const clearEdit = useCallback(() => {
    setEditingId(null)
    setEditForm(emptyStaffForm())
    setEditError(null)
    setEditSubmitting(false)
  }, [])

  const startEdit = useCallback((row: StaffListItem) => {
    setCreateOpen(false)
    setCreateForm(emptyStaffForm())
    setCreateError(null)
    setCreateSubmitting(false)
    setEditingId(row.id)
    setEditForm(staffFormFromRow(row))
    setEditError(null)
  }, [])

  const handleCreateSubmit = useCallback(
    async (event: FormEvent) => {
      event.preventDefault()
      if (!session || !canWrite || !createOpen || createSubmitting) {
        return
      }

      const parsed = parseStaffFormFields(createForm)
      if (typeof parsed === 'string') {
        setCreateError(parsed)
        return
      }

      setCreateSubmitting(true)
      setCreateError(null)
      try {
        await createAdminStaff(
          session.token,
          session.salon.salon_id,
          buildStaffCreateBody(parsed),
        )
        clearCreate()
        await load()
      } catch (err) {
        if (isUnauthorizedError(err)) {
          clearAuthAndRedirect()
          return
        }
        setCreateError(mapAdminStaffCreateError(err))
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
        setEditError(t('admin.staff.stale'))
        return
      }

      const parsed = parseStaffFormFields(editForm)
      if (typeof parsed === 'string') {
        setEditError(parsed)
        return
      }

      if (hasStaffUnsupportedClear(original, parsed)) {
        setEditError(STAFF_UNSUPPORTED_CLEAR_MESSAGE)
        return
      }

      const patchBody = buildStaffUpdatePatch(original, parsed)
      if (Object.keys(patchBody).length === 0) {
        clearEdit()
        return
      }

      setEditSubmitting(true)
      setEditError(null)
      try {
        await patchAdminStaff(
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
        setEditError(mapAdminStaffUpdateError(err))
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

  const performActiveToggle = useCallback(
    async (row: StaffListItem) => {
      if (!session || !canWrite || togglingActiveId !== null) {
        return
      }

      setDeactivateConfirmId((current) => (current === row.id ? null : current))
      setTogglingActiveId(row.id)
      setToggleActiveErrors((prev) => {
        if (prev[row.id] === undefined) {
          return prev
        }
        const next = { ...prev }
        delete next[row.id]
        return next
      })

      try {
        await patchAdminStaff(
          session.token,
          session.salon.salon_id,
          row.id,
          staffActiveTogglePatch(row.is_active),
        )
        await load()
      } catch (err) {
        if (isUnauthorizedError(err)) {
          clearAuthAndRedirect()
          return
        }
        setToggleActiveErrors((prev) => ({
          ...prev,
          [row.id]: mapAdminStaffUpdateError(err),
        }))
      } finally {
        setTogglingActiveId(null)
      }
    },
    [session, canWrite, togglingActiveId, load, clearAuthAndRedirect],
  )

  const handleActiveToggleClick = useCallback(
    (row: StaffListItem) => {
      if (!session || !canWrite || formBusy) {
        return
      }
      if (row.is_active) {
        setDeactivateConfirmId(row.id)
        setToggleActiveErrors((prev) => {
          if (prev[row.id] === undefined) {
            return prev
          }
          const next = { ...prev }
          delete next[row.id]
          return next
        })
        return
      }
      void performActiveToggle(row)
    },
    [session, canWrite, formBusy, performActiveToggle],
  )

  const cancelDeactivateConfirm = useCallback(() => {
    setDeactivateConfirmId(null)
  }, [])

  const handleToggleBookable = useCallback(
    async (row: StaffListItem) => {
      if (!session || !canWrite || togglingBookableId !== null || formBusy) {
        return
      }

      setTogglingBookableId(row.id)
      setToggleBookableErrors((prev) => {
        if (prev[row.id] === undefined) {
          return prev
        }
        const next = { ...prev }
        delete next[row.id]
        return next
      })

      try {
        await patchAdminStaff(
          session.token,
          session.salon.salon_id,
          row.id,
          staffBookableTogglePatch(row.is_bookable),
        )
        await load()
      } catch (err) {
        if (isUnauthorizedError(err)) {
          clearAuthAndRedirect()
          return
        }
        setToggleBookableErrors((prev) => ({
          ...prev,
          [row.id]: mapAdminStaffUpdateError(err),
        }))
      } finally {
        setTogglingBookableId(null)
      }
    },
    [session, canWrite, togglingBookableId, formBusy, load, clearAuthAndRedirect],
  )

  const editingRow =
    editingId !== null ? items.find((row) => row.id === editingId) : undefined

  return (
    <AdminLayout>
      <section className="admin-staff">
        <header className="admin-staff__header">
          <h1 className="admin-staff__title">{t('admin.staff.title')}</h1>
          <p className="admin-staff__lead">{t('admin.staff.lead')}</p>
          {canWrite && !createOpen && editingId === null ? (
            <p className="admin-staff__header-actions">
              <button
                type="button"
                className="btn btn--primary btn--compact"
                onClick={startCreate}
                disabled={formBusy}
              >
                {t('admin.staff.add')}
              </button>
            </p>
          ) : null}
        </header>

        {canWrite && createOpen ? (
          <form
            className="admin-staff__form"
            onSubmit={(event) => void handleCreateSubmit(event)}
            aria-labelledby="admin-staff-create-title"
          >
            <h2 id="admin-staff-create-title" className="admin-staff__form-title">
              {t('admin.staff.add')}
            </h2>
            <p className="admin-staff__form-lead">
              {t('admin.staff.createLead')}
            </p>
            {createError ? (
              <p className="admin-staff__form-error" role="alert">
                {createError}
              </p>
            ) : null}
            <StaffFormFields
              form={createForm}
              onChange={setCreateForm}
              disabled={createSubmitting}
              idPrefix="staff-create"
            />
            <div className="admin-staff__form-actions">
              <button
                type="submit"
                className="btn btn--primary btn--compact"
                disabled={createSubmitting}
                aria-busy={createSubmitting}
              >
                {createSubmitting ? t('common.creating') : t('admin.staff.create')}
              </button>
              <button
                type="button"
                className="btn btn--secondary btn--compact"
                onClick={clearCreate}
                disabled={createSubmitting}
              >
                {t('common.cancel')}
              </button>
            </div>
          </form>
        ) : null}

        {canWrite && editingId !== null ? (
          <form
            className="admin-staff__form"
            onSubmit={(event) => void handleEditSubmit(event)}
            aria-labelledby="admin-staff-edit-title"
          >
            <h2 id="admin-staff-edit-title" className="admin-staff__form-title">
              {t('admin.staff.edit')}{editingRow ? `: ${editingRow.display_name}` : ''}
            </h2>
            <p className="admin-staff__form-lead">
              {t('admin.staff.editLead')}
            </p>
            {editError ? (
              <p className="admin-staff__form-error" role="alert">
                {editError}
              </p>
            ) : null}
            <StaffFormFields
              form={editForm}
              onChange={setEditForm}
              disabled={editSubmitting}
              idPrefix="staff-edit"
            />
            <div className="admin-staff__form-actions">
              <button
                type="submit"
                className="btn btn--primary btn--compact"
                disabled={editSubmitting}
                aria-busy={editSubmitting}
              >
                {editSubmitting ? t('common.saving') : t('admin.staff.saveChanges')}
              </button>
              <button
                type="button"
                className="btn btn--secondary btn--compact"
                onClick={clearEdit}
                disabled={editSubmitting}
              >
                {t('common.cancel')}
              </button>
            </div>
          </form>
        ) : null}

        {mediaIndex.error ? (
          <p className="admin-staff__state admin-staff__state--error" role="alert">
            {mediaIndex.error}
          </p>
        ) : null}

        <div className="admin-staff__filters">
          <label className="admin-staff__filter admin-staff__filter--checkbox">
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(event) => setShowInactive(event.target.checked)}
            />
            <span>{t('admin.form.showInactive')}</span>
          </label>
        </div>

        {loading ? (
          <p className="admin-staff__state" role="status">
            {t('admin.staff.loading')}
          </p>
        ) : null}

        {!loading && error ? (
          <p className="admin-staff__state admin-staff__state--error" role="alert">
            {error}
          </p>
        ) : null}

        {!loading && !error && items.length === 0 ? (
          <p className="admin-staff__state">{t('admin.staff.empty')}</p>
        ) : null}

        {!loading && !error && items.length > 0 ? (
          <div className="admin-staff__table-wrap">
            <table className="admin-staff__table">
              <thead>
                <tr>
                  <th scope="col">{t('admin.staff.colName')}</th>
                  <th scope="col">{t('admin.staff.colTitle')}</th>
                  <th scope="col">{t('admin.staff.colActive')}</th>
                  <th scope="col">{t('admin.staff.colBookable')}</th>
                  <th scope="col">{t('admin.staff.avatar')}</th>
                  {canWrite ? <th scope="col">{t('common.actions')}</th> : null}
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
                    <td>
                      {session ? (
                        <AdminEntityMediaAttach
                          token={session.token}
                          salonId={session.salon.salon_id}
                          canWrite={canWrite}
                          entityType="staff"
                          entityId={row.id}
                          purpose="avatar"
                          label={t('admin.staff.avatar')}
                          assets={mediaIndex.assets}
                          attachment={mediaIndex.getAttachment(
                            'staff',
                            row.id,
                            'avatar',
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
                        <div className="admin-staff__row-actions">
                          <button
                            type="button"
                            className="btn btn--secondary btn--compact"
                            onClick={() => startEdit(row)}
                            disabled={
                              formBusy || (editingId !== null && editingId !== row.id)
                            }
                          >
                            {t('common.edit')}
                          </button>
                          {deactivateConfirmId === row.id && row.is_active ? (
                            <div
                              className="admin-staff__deactivate-confirm"
                              role="group"
                              aria-labelledby={`staff-deactivate-confirm-${row.id}`}
                            >
                              <p
                                id={`staff-deactivate-confirm-${row.id}`}
                                className="admin-staff__deactivate-confirm-text"
                              >
                                {t('admin.staff.deactivateConfirm', { name: row.display_name })}
                              </p>
                              <div className="admin-staff__row-actions">
                                <button
                                  type="button"
                                  className="btn btn--secondary btn--compact"
                                  onClick={cancelDeactivateConfirm}
                                  disabled={togglingActiveId === row.id}
                                >
                                  {t('common.cancel')}
                                </button>
                                <button
                                  type="button"
                                  className="btn btn--primary btn--compact"
                                  onClick={() => void performActiveToggle(row)}
                                  disabled={togglingActiveId === row.id}
                                  aria-busy={togglingActiveId === row.id}
                                >
                                  {togglingActiveId === row.id
                                    ? t('admin.staff.deactivating')
                                    : t('admin.staff.confirmDeactivate')}
                                </button>
                              </div>
                            </div>
                          ) : (
                            <button
                              type="button"
                              className="btn btn--secondary btn--compact"
                              onClick={() => handleActiveToggleClick(row)}
                              disabled={formBusy || editingId === row.id}
                              aria-busy={
                                togglingActiveId === row.id && !row.is_active
                              }
                            >
                              {togglingActiveId === row.id && !row.is_active
                                ? t('admin.staff.activating')
                                : staffActiveToggleLabel(row.is_active)}
                            </button>
                          )}
                          <button
                            type="button"
                            className="btn btn--secondary btn--compact"
                            onClick={() => void handleToggleBookable(row)}
                            disabled={formBusy || editingId === row.id}
                            aria-busy={togglingBookableId === row.id}
                          >
                            {togglingBookableId === row.id
                              ? row.is_bookable
                                ? t('admin.staff.updating')
                                : t('admin.staff.updating')
                              : staffBookableToggleLabel(row.is_bookable)}
                          </button>
                        </div>
                        {toggleActiveErrors[row.id] ? (
                          <p className="admin-staff__row-action-error" role="alert">
                            {toggleActiveErrors[row.id]}
                          </p>
                        ) : null}
                        {toggleBookableErrors[row.id] ? (
                          <p className="admin-staff__row-action-error" role="alert">
                            {toggleBookableErrors[row.id]}
                          </p>
                        ) : null}
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
