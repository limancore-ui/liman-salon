import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { isUnauthorizedError } from '../api/auth'
import {
  createAdminShowcaseItem,
  deleteAdminShowcaseItem,
  fetchAdminShowcaseItems,
  patchAdminShowcaseItem,
  publishAdminShowcaseItem,
  unpublishAdminShowcaseItem,
} from '../api/adminShowcase'
import { fetchAdminMediaList } from '../api/media'
import { AdminLayout } from '../components/AdminLayout'
import { AdminMediaPreview } from '../components/AdminMediaPreview'
import { t, type MessageKey } from '../i18n'
import type {
  AdminShowcaseCategory,
  AdminShowcaseCreateBody,
  AdminShowcaseItem,
  AdminShowcasePatchBody,
} from '../types/adminShowcase'
import type { MediaAssetResponse } from '../types/media'
import { adminUserErrorMessage } from '../utils/adminUserError'
import { formatDashboardPrice } from '../utils/adminSalonFormat'

const PAGE_SIZE = 50
const MAX_INTEGER = 2_147_483_647

type ShowcaseForm = {
  title: string
  category: AdminShowcaseCategory
  description: string
  priceMajor: string
  mediaAssetId: string
  sortOrder: string
}

type ParsedValue<T> = { ok: true; value: T } | { ok: false }

const EMPTY_FORM: ShowcaseForm = {
  title: '',
  category: 'work',
  description: '',
  priceMajor: '',
  mediaAssetId: '',
  sortOrder: '0',
}

function canManageShowcase(role: string | undefined): boolean {
  return role === 'owner' || role === 'admin'
}

function parseOptionalPriceCents(raw: string): ParsedValue<number | null> {
  const value = raw.trim()
  if (value === '') {
    return { ok: true, value: null }
  }
  const amount = Number(value)
  if (!Number.isFinite(amount) || amount < 0) {
    return { ok: false }
  }
  const cents = Math.round(amount * 100)
  if (!Number.isSafeInteger(cents) || cents > MAX_INTEGER) {
    return { ok: false }
  }
  return { ok: true, value: cents }
}

function parseSortOrder(raw: string): ParsedValue<number> {
  const value = raw.trim()
  if (value === '') {
    return { ok: false }
  }
  const parsed = Number(value)
  if (!Number.isInteger(parsed) || parsed < 0 || parsed > MAX_INTEGER) {
    return { ok: false }
  }
  return { ok: true, value: parsed }
}

function categoryLabel(category: AdminShowcaseCategory): string {
  const labels: Record<AdminShowcaseCategory, MessageKey> = {
    work: 'admin.showcase.category.work',
    cosmetics: 'admin.showcase.category.cosmetics',
    dyes: 'admin.showcase.category.dyes',
    varnishes: 'admin.showcase.category.varnishes',
  }
  return t(labels[category])
}

function formFromItem(item: AdminShowcaseItem): ShowcaseForm {
  return {
    title: item.title,
    category: item.category,
    description: item.description ?? '',
    priceMajor: item.price_cents === null ? '' : String(item.price_cents / 100),
    mediaAssetId: item.media_asset_id,
    sortOrder: String(item.sort_order),
  }
}

export function AdminShowcasePage() {
  const { session, clearAuthAndRedirect } = useAuth()
  const salonId = session?.salon.salon_id
  const canManage = canManageShowcase(session?.salon.role)

  const [items, setItems] = useState<AdminShowcaseItem[]>([])
  const [itemsLoading, setItemsLoading] = useState(true)
  const [itemsSalonId, setItemsSalonId] = useState<string | null>(null)
  const [itemsError, setItemsError] = useState<string | null>(null)
  const [itemsOffset, setItemsOffset] = useState(0)
  const [itemsHasMore, setItemsHasMore] = useState(false)
  const [itemsLoadingMore, setItemsLoadingMore] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busyItemId, setBusyItemId] = useState<string | null>(null)

  const [mediaAssets, setMediaAssets] = useState<MediaAssetResponse[]>([])
  const [mediaLoading, setMediaLoading] = useState(false)
  const [mediaError, setMediaError] = useState<string | null>(null)
  const [mediaOffset, setMediaOffset] = useState(0)
  const [mediaHasMore, setMediaHasMore] = useState(false)

  const [formOpen, setFormOpen] = useState(false)
  const [formSalonId, setFormSalonId] = useState<string | null>(null)
  const [editingItem, setEditingItem] = useState<AdminShowcaseItem | null>(null)
  const [form, setForm] = useState<ShowcaseForm>(EMPTY_FORM)
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const listRequestId = useRef(0)
  const mediaRequestId = useRef(0)

  const loadItems = useCallback(async () => {
    if (!session) {
      return
    }
    const requestId = ++listRequestId.current
    try {
      const rows = await fetchAdminShowcaseItems(session.token, session.salon.salon_id, {
        limit: PAGE_SIZE,
        offset: 0,
      })
      if (requestId !== listRequestId.current) {
        return
      }
      const tenantRows = rows.filter((row) => row.salon_id === session.salon.salon_id)
      setItems(tenantRows)
      setItemsSalonId(session.salon.salon_id)
      setItemsError(null)
      setItemsOffset(rows.length)
      setItemsHasMore(rows.length === PAGE_SIZE)
    } catch (error) {
      if (requestId !== listRequestId.current) {
        return
      }
      if (isUnauthorizedError(error)) {
        clearAuthAndRedirect()
        return
      }
      setItems([])
      setItemsSalonId(session.salon.salon_id)
      setItemsOffset(0)
      setItemsHasMore(false)
      setItemsError(adminUserErrorMessage(error, 'admin.showcase.loadFailed'))
    } finally {
      if (requestId === listRequestId.current) {
        setItemsLoading(false)
      }
    }
  }, [session, clearAuthAndRedirect])

  const loadMedia = useCallback(
    async (append = false) => {
      if (!session || !canManage) {
        return
      }
      const requestId = ++mediaRequestId.current
      const offset = append ? mediaOffset : 0
      setMediaLoading(true)
      setMediaError(null)
      try {
        const rows = await fetchAdminMediaList(session.token, session.salon.salon_id, {
          limit: PAGE_SIZE,
          offset,
        })
        if (requestId !== mediaRequestId.current) {
          return
        }
        const tenantRows = rows.filter((asset) => asset.salon_id === session.salon.salon_id)
        setMediaAssets((current) => {
          if (!append) {
            return tenantRows
          }
          const existingIds = new Set(current.map((asset) => asset.id))
          return [...current, ...tenantRows.filter((asset) => !existingIds.has(asset.id))]
        })
        setMediaOffset(offset + rows.length)
        setMediaHasMore(rows.length === PAGE_SIZE)
      } catch (error) {
        if (requestId !== mediaRequestId.current) {
          return
        }
        if (isUnauthorizedError(error)) {
          clearAuthAndRedirect()
          return
        }
        setMediaError(adminUserErrorMessage(error, 'admin.showcase.mediaLoadFailed'))
      } finally {
        if (requestId === mediaRequestId.current) {
          setMediaLoading(false)
        }
      }
    }, [session, canManage, mediaOffset, clearAuthAndRedirect],
  )

  // The list request is asynchronous; it updates state only after the API promise settles.
  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect
    void loadItems()
  }, [loadItems])

  useEffect(() => {
    mediaRequestId.current += 1
  }, [salonId])

  useEffect(
    () => () => {
      listRequestId.current += 1
      mediaRequestId.current += 1
    },
    [],
  )

  async function loadMoreItems() {
    if (!session || itemsLoadingMore || !itemsHasMore) {
      return
    }
    const requestId = listRequestId.current
    setItemsLoadingMore(true)
    setActionError(null)
    try {
      const rows = await fetchAdminShowcaseItems(session.token, session.salon.salon_id, {
        limit: PAGE_SIZE,
        offset: itemsOffset,
      })
      if (requestId !== listRequestId.current) {
        return
      }
      setItems((current) => [
        ...current,
        ...rows.filter(
          (row) => row.salon_id === salonId && !current.some((item) => item.id === row.id),
        ),
      ])
      setItemsOffset(itemsOffset + rows.length)
      setItemsHasMore(rows.length === PAGE_SIZE)
    } catch (error) {
      if (isUnauthorizedError(error)) {
        clearAuthAndRedirect()
      } else {
        setActionError(adminUserErrorMessage(error, 'admin.showcase.loadFailed'))
      }
    } finally {
      setItemsLoadingMore(false)
    }
  }

  function openCreateForm() {
    if (!canManage) {
      return
    }
    setFormOpen(true)
    setFormSalonId(salonId ?? null)
    setEditingItem(null)
    setForm(EMPTY_FORM)
    setFormError(null)
    setNotice(null)
    void loadMedia(false)
  }

  function openEditForm(item: AdminShowcaseItem) {
    if (!canManage) {
      return
    }
    setFormOpen(true)
    setFormSalonId(salonId ?? null)
    setEditingItem(item)
    setForm(formFromItem(item))
    setFormError(null)
    setNotice(null)
    void loadMedia(false)
  }

  function closeForm() {
    if (saving) {
      return
    }
    setFormOpen(false)
    setFormSalonId(null)
    setEditingItem(null)
    setFormError(null)
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!session || !canManage || saving) {
      return
    }
    const title = form.title.trim()
    if (!title) {
      setFormError(t('admin.showcase.titleRequired'))
      return
    }
    if (title.length > 200) {
      setFormError(t('admin.showcase.titleTooLong'))
      return
    }
    const price = parseOptionalPriceCents(form.priceMajor)
    if (!price.ok) {
      setFormError(t('admin.showcase.priceInvalid'))
      return
    }
    const sortOrder = parseSortOrder(form.sortOrder)
    if (!sortOrder.ok) {
      setFormError(t('admin.showcase.sortInvalid'))
      return
    }
    const selectedAssetIsActive = mediaAssets.some(
      (asset) => asset.id === form.mediaAssetId && asset.salon_id === salonId,
    )
    const mediaUnchanged = editingItem?.media_asset_id === form.mediaAssetId
    if (!form.mediaAssetId || (!selectedAssetIsActive && !mediaUnchanged)) {
      setFormError(t('admin.showcase.imageRequired'))
      return
    }

    const description = form.description.trim() || null
    setSaving(true)
    setFormError(null)
    setActionError(null)
    setNotice(null)
    try {
      if (editingItem) {
        const changes: AdminShowcasePatchBody = {}
        if (title !== editingItem.title) changes.title = title
        if (description !== editingItem.description) changes.description = description
        if (form.category !== editingItem.category) changes.category = form.category
        if (price.value !== editingItem.price_cents) changes.price_cents = price.value
        if (form.mediaAssetId !== editingItem.media_asset_id) {
          changes.media_asset_id = form.mediaAssetId
        }
        if (sortOrder.value !== editingItem.sort_order) {
          changes.sort_order = sortOrder.value
        }
        if (Object.keys(changes).length === 0) {
          setFormError(t('admin.showcase.noChanges'))
          return
        }
        await patchAdminShowcaseItem(
          session.token,
          session.salon.salon_id,
          editingItem.id,
          changes,
        )
        setNotice(t('admin.showcase.updated'))
      } else {
        const body: AdminShowcaseCreateBody = {
          category: form.category,
          title,
          media_asset_id: form.mediaAssetId,
          description,
          price_cents: price.value,
          sort_order: sortOrder.value,
        }
        await createAdminShowcaseItem(
          session.token,
          session.salon.salon_id,
          body,
        )
        setNotice(t('admin.showcase.created'))
      }
      setFormOpen(false)
      setFormSalonId(null)
      setEditingItem(null)
      setItemsLoading(true)
      await loadItems()
    } catch (error) {
      if (isUnauthorizedError(error)) {
        clearAuthAndRedirect()
        return
      }
      setFormError(adminUserErrorMessage(error, 'admin.showcase.actionFailed'))
    } finally {
      setSaving(false)
    }
  }

  async function changePublication(item: AdminShowcaseItem) {
    if (!session || !canManage || busyItemId) {
      return
    }
    setBusyItemId(item.id)
    setActionError(null)
    setNotice(null)
    try {
      if (item.is_published) {
        await unpublishAdminShowcaseItem(
          session.token,
          session.salon.salon_id,
          item.id,
        )
        setNotice(t('admin.showcase.hidden'))
      } else {
        await publishAdminShowcaseItem(
          session.token,
          session.salon.salon_id,
          item.id,
        )
        setNotice(t('admin.showcase.published'))
      }
      setItemsLoading(true)
      await loadItems()
    } catch (error) {
      if (isUnauthorizedError(error)) {
        clearAuthAndRedirect()
        return
      }
      setActionError(adminUserErrorMessage(error, 'admin.showcase.actionFailed'))
    } finally {
      setBusyItemId(null)
    }
  }

  async function removeItem(item: AdminShowcaseItem) {
    if (!session || !canManage || busyItemId) {
      return
    }
    if (!window.confirm(t('admin.showcase.deleteConfirm', { title: item.title }))) {
      return
    }
    setBusyItemId(item.id)
    setActionError(null)
    setNotice(null)
    try {
      await deleteAdminShowcaseItem(
        session.token,
        session.salon.salon_id,
        item.id,
      )
      setNotice(t('admin.showcase.deleted'))
      setItemsLoading(true)
      await loadItems()
    } catch (error) {
      if (isUnauthorizedError(error)) {
        clearAuthAndRedirect()
        return
      }
      setActionError(adminUserErrorMessage(error, 'admin.showcase.actionFailed'))
    } finally {
      setBusyItemId(null)
    }
  }

  const salonItems = items.filter((item) => item.salon_id === salonId)
  const salonMediaAssets = mediaAssets.filter((asset) => asset.salon_id === salonId)
  const selectedMedia = salonMediaAssets.find((asset) => asset.id === form.mediaAssetId)
  const isItemsLoading = itemsLoading || (salonId !== undefined && itemsSalonId !== salonId)
  const isFormOpen = formOpen && formSalonId === salonId && canManage

  return (
    <AdminLayout>
      <section className="admin-showcase" aria-labelledby="admin-showcase-title">
        <header className="admin-showcase__header">
          <div>
            <h1 id="admin-showcase-title" className="admin-showcase__title">
              {t('admin.showcase.title')}
            </h1>
            <p className="admin-showcase__lead">{t('admin.showcase.lead')}</p>
          </div>
          {canManage ? (
            <button
              type="button"
              className="btn btn--primary"
              onClick={openCreateForm}
            >
              {t('admin.showcase.create')}
            </button>
          ) : null}
        </header>

        {!canManage ? (
          <p className="admin-showcase__readonly">{t('admin.showcase.readOnly')}</p>
        ) : null}
        {actionError ? (
          <p className="admin-showcase__state admin-showcase__state--error" role="alert">
            {actionError}
          </p>
        ) : null}
        {notice ? (
          <p className="admin-showcase__notice" role="status">
            {notice}
          </p>
        ) : null}

        {isFormOpen ? (
          <form className="admin-showcase__form" onSubmit={(event) => void handleSubmit(event)}>
            <h2 className="admin-showcase__form-title">
              {editingItem ? t('admin.showcase.edit') : t('admin.showcase.create')}
            </h2>
            <div className="admin-showcase__form-grid">
              <label className="form-field">
                <span className="form-field__label">
                  {t('admin.showcase.titleField')} <span className="form-field__required">*</span>
                </span>
                <input
                  className="form-field__input"
                  type="text"
                  required
                  maxLength={200}
                  value={form.title}
                  disabled={saving}
                  onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
                />
              </label>
              <label className="form-field">
                <span className="form-field__label">{t('admin.showcase.categoryField')}</span>
                <select
                  className="form-field__input"
                  value={form.category}
                  disabled={saving}
                  onChange={(event) => setForm((current) => ({
                    ...current,
                    category: event.target.value as AdminShowcaseCategory,
                  }))}
                >
                  {(['work', 'cosmetics', 'dyes', 'varnishes'] as const).map((category) => (
                    <option key={category} value={category}>{categoryLabel(category)}</option>
                  ))}
                </select>
              </label>
              <div className="form-field admin-showcase__field-wide">
                <label className="form-field__label" htmlFor="admin-showcase-media">
                  {t('admin.showcase.imageField')}{!editingItem ? ' *' : ''}
                </label>
                <select
                  id="admin-showcase-media"
                  className="form-field__input"
                  required={!editingItem}
                  value={form.mediaAssetId}
                  disabled={saving || mediaLoading || salonMediaAssets.length === 0}
                  onChange={(event) => setForm((current) => ({ ...current, mediaAssetId: event.target.value }))}
                >
                  <option value="">{t('admin.showcase.chooseImage')}</option>
                  {editingItem && !salonMediaAssets.some((asset) => asset.id === editingItem.media_asset_id) ? (
                    <option value={editingItem.media_asset_id} disabled>
                      {t('admin.showcase.currentImageNotListed')}
                    </option>
                  ) : null}
                  {salonMediaAssets.map((asset) => (
                    <option key={asset.id} value={asset.id}>{asset.original_filename}</option>
                  ))}
                </select>
                {mediaLoading ? <span className="form-field__hint" role="status">{t('admin.showcase.mediaLoading')}</span> : null}
                {mediaError ? (
                  <span className="form-field__error" role="alert">
                    {mediaError}{' '}
                    <button type="button" className="admin-showcase__inline-button" onClick={() => void loadMedia(false)}>
                      {t('common.retry')}
                    </button>
                  </span>
                ) : null}
                {!mediaLoading && !mediaError && salonMediaAssets.length === 0 ? (
                  <span className="form-field__hint">
                    {t('admin.showcase.noMedia')}{' '}
                    <Link to="/admin/media">{t('admin.showcase.openMedia')}</Link>
                  </span>
                ) : null}
                {mediaHasMore && salonMediaAssets.length > 0 ? (
                  <button
                    type="button"
                    className="admin-showcase__inline-button"
                    disabled={mediaLoading}
                    onClick={() => void loadMedia(true)}
                  >
                    {t('admin.showcase.loadMoreMedia')}
                  </button>
                ) : null}
                {selectedMedia && session ? (
                  <AdminMediaPreview
                    token={session.token}
                    salonId={session.salon.salon_id}
                    mediaId={selectedMedia.id}
                    alt={selectedMedia.original_filename}
                    className="admin-showcase__form-image"
                  />
                ) : null}
              </div>
              <label className="form-field admin-showcase__field-wide">
                <span className="form-field__label">{t('admin.showcase.descriptionField')}</span>
                <textarea
                  className="form-field__input form-field__textarea"
                  value={form.description}
                  disabled={saving}
                  onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                />
              </label>
              <label className="form-field">
                <span className="form-field__label">{t('admin.showcase.priceField')}</span>
                <input
                  className="form-field__input"
                  type="number"
                  min="0"
                  step="0.01"
                  inputMode="decimal"
                  value={form.priceMajor}
                  disabled={saving}
                  onChange={(event) => setForm((current) => ({ ...current, priceMajor: event.target.value }))}
                />
              </label>
              <label className="form-field">
                <span className="form-field__label">{t('admin.showcase.sortOrderField')}</span>
                <input
                  className="form-field__input"
                  type="number"
                  min="0"
                  step="1"
                  value={form.sortOrder}
                  disabled={saving}
                  onChange={(event) => setForm((current) => ({ ...current, sortOrder: event.target.value }))}
                />
              </label>
            </div>
            {formError ? <p className="admin-showcase__form-error" role="alert">{formError}</p> : null}
            <div className="admin-showcase__form-actions">
              <button type="submit" className="btn btn--primary" disabled={saving}>
                {saving ? t('common.saving') : t('admin.showcase.save')}
              </button>
              <button type="button" className="btn btn--secondary" disabled={saving} onClick={closeForm}>
                {t('common.cancel')}
              </button>
            </div>
          </form>
        ) : null}

        {isItemsLoading ? (
          <p className="admin-showcase__state" role="status">{t('admin.showcase.loading')}</p>
        ) : null}
        {!isItemsLoading && itemsError ? (
          <div className="admin-showcase__state admin-showcase__state--error" role="alert">
            <p>{itemsError}</p>
            <button type="button" className="btn btn--secondary" onClick={() => {
              setItemsLoading(true)
              void loadItems()
            }}>
              {t('common.retry')}
            </button>
          </div>
        ) : null}
        {!isItemsLoading && !itemsError && salonItems.length === 0 ? (
          <p className="admin-showcase__state">{t('admin.showcase.empty')}</p>
        ) : null}
        {!isItemsLoading && !itemsError && salonItems.length > 0 ? (
          <>
            <ul className="admin-showcase__grid">
              {salonItems.map((item) => (
                <li key={item.id} className="admin-showcase__card">
                  {session ? (
                    <AdminMediaPreview
                      token={session.token}
                      salonId={session.salon.salon_id}
                      mediaId={item.media_asset_id}
                      alt={item.title}
                      className="admin-showcase__image"
                    />
                  ) : null}
                  <div className="admin-showcase__card-content">
                    <div className="admin-showcase__badges">
                      <span className="admin-showcase__badge">{categoryLabel(item.category)}</span>
                      <span className={`admin-showcase__badge ${item.is_published ? 'admin-showcase__badge--published' : ''}`}>
                        {item.is_published ? t('admin.showcase.publishedStatus') : t('admin.showcase.hiddenStatus')}
                      </span>
                    </div>
                    <h2 className="admin-showcase__item-title">{item.title}</h2>
                    {item.description ? <p className="admin-showcase__description">{item.description}</p> : null}
                    {item.price_cents !== null ? (
                      <p className="admin-showcase__price">
                        {formatDashboardPrice(item.price_cents, session?.salon.currency_code)}
                      </p>
                    ) : null}
                    <p className="admin-showcase__sort-order">
                      {t('admin.showcase.sortOrderValue', { value: item.sort_order })}
                    </p>
                    {canManage ? (
                      <div className="admin-showcase__actions">
                        <button type="button" className="btn btn--secondary btn--compact" disabled={busyItemId !== null} onClick={() => openEditForm(item)}>
                          {t('admin.showcase.edit')}
                        </button>
                        <button type="button" className="btn btn--secondary btn--compact" disabled={busyItemId !== null} onClick={() => void changePublication(item)}>
                          {item.is_published ? t('admin.showcase.unpublish') : t('admin.showcase.publish')}
                        </button>
                        <button type="button" className="btn btn--secondary btn--compact" disabled={busyItemId !== null} onClick={() => void removeItem(item)}>
                          {busyItemId === item.id ? t('common.deleting') : t('common.delete')}
                        </button>
                      </div>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
            {itemsHasMore ? (
              <div className="admin-showcase__load-more">
                <button type="button" className="btn btn--secondary" disabled={itemsLoadingMore} onClick={() => void loadMoreItems()}>
                  {itemsLoadingMore ? t('admin.showcase.loadingMore') : t('admin.showcase.loadMore')}
                </button>
              </div>
            ) : null}
          </>
        ) : null}
      </section>
    </AdminLayout>
  )
}
