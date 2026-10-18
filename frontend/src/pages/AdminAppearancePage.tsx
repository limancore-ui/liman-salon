import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { AdminLayout } from '../components/AdminLayout'
import { AdminEntityMediaAttach } from '../components/AdminEntityMediaAttach'
import { AdminMediaPreview } from '../components/AdminMediaPreview'
import { useAuth } from '../auth/AuthContext'
import {
  fetchSalonAppearance,
  patchSalonAppearance,
} from '../api/salonAppearance'
import { patchSalonProfile } from '../api/salonProfile'
import { isUnauthorizedError } from '../api/auth'
import { useSalonMediaAttachmentIndex } from '../hooks/useSalonMediaAttachmentIndex'
import { adminUserErrorMessage } from '../utils/adminUserError'
import { parseOptionalHexColor } from '../utils/salonAppearanceColors'
import {
  buildSalonThemeStyle,
  hintsFromPublicSalonAppearance,
} from '../utils/salonPublicTheme'
import { resolvePublicMediaUrl } from '../utils/publicMedia'
import type { SalonAppearance } from '../types/salonAppearance'
import { t } from '../i18n'

const NAME_MAX_LENGTH = 200

const PRESET_PRIMARY = [
  '#2f6b4f',
  '#1e4d7b',
  '#6b5a3e',
  '#4a5568',
  '#8b3a3a',
] as const

function canManageAppearance(role: string | undefined): boolean {
  return role === 'owner' || role === 'admin'
}

export function AdminAppearancePage() {
  const { session, clearAuthAndRedirect, refreshSession } = useAuth()
  const [appearance, setAppearance] = useState<SalonAppearance | null>(null)
  const [nameInput, setNameInput] = useState('')
  const [primaryInput, setPrimaryInput] = useState('')
  const [accentInput, setAccentInput] = useState('')
  const [backgroundInput, setBackgroundInput] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [savingName, setSavingName] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)

  const canWrite = canManageAppearance(session?.salon.role)
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
    setSaveMessage(null)
    try {
      const data = await fetchSalonAppearance(
        session.token,
        session.salon.salon_id,
      )
      setAppearance(data)
      setNameInput(data.salon_name)
      setPrimaryInput(data.primary_color ?? '')
      setAccentInput(data.accent_soft_color ?? '')
      setBackgroundInput(data.background_color ?? '')
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      setError(adminUserErrorMessage(err, 'admin.appearance.loadFailed'))
      setAppearance(null)
    } finally {
      setLoading(false)
    }
  }, [session, clearAuthAndRedirect])

  useEffect(() => {
    void load()
  }, [load])

  const logoAttachment =
    session != null
      ? mediaIndex.getAttachment('salon', session.salon.salon_id, 'logo')
      : null
  const coverAttachment =
    session != null
      ? mediaIndex.getAttachment('salon', session.salon.salon_id, 'cover')
      : null

  const previewHints = useMemo(() => {
    const primary = parseOptionalHexColor(primaryInput)
    const accent = parseOptionalHexColor(accentInput)
    const background = parseOptionalHexColor(backgroundInput)
    const slug = session?.salon.salon_slug
    const coverUrl =
      slug && coverAttachment
        ? resolvePublicMediaUrl(slug, coverAttachment.mediaId)
        : null
    return hintsFromPublicSalonAppearance(
      {
        primary_color: primary.ok ? primary.color : null,
        accent_soft_color: accent.ok ? accent.color : null,
        background_color: background.ok ? background.color : null,
      },
      coverUrl,
    )
  }, [
    primaryInput,
    accentInput,
    backgroundInput,
    coverAttachment,
    session?.salon.salon_slug,
  ])

  const previewStyle = buildSalonThemeStyle(previewHints)
  const previewName = appearance?.salon_name ?? ''

  async function handleSaveName(event: React.FormEvent) {
    event.preventDefault()
    if (!session || !canWrite || !appearance) {
      return
    }
    const trimmed = nameInput.trim()
    if (!trimmed) {
      setError(t('admin.appearance.nameEmpty'))
      return
    }
    if (trimmed.length > NAME_MAX_LENGTH) {
      setError(t('admin.appearance.nameTooLong', { max: NAME_MAX_LENGTH }))
      return
    }
    if (trimmed === appearance.salon_name) {
      setSaveMessage(t('admin.appearance.nameUnchanged'))
      return
    }
    setSavingName(true)
    setError(null)
    setSaveMessage(null)
    try {
      const updated = await patchSalonProfile(
        session.token,
        session.salon.salon_id,
        { name: trimmed },
      )
      setAppearance({ ...appearance, salon_name: updated.name })
      setNameInput(updated.name)
      setSaveMessage(t('admin.appearance.nameSaved'))
      await refreshSession()
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      setError(adminUserErrorMessage(err, 'admin.appearance.nameSaveFailed'))
    } finally {
      setSavingName(false)
    }
  }

  async function handleSave(event: React.FormEvent) {
    event.preventDefault()
    if (!session || !canWrite) {
      return
    }
    const primary = parseOptionalHexColor(primaryInput)
    const accent = parseOptionalHexColor(accentInput)
    const background = parseOptionalHexColor(backgroundInput)
    if (!primary.ok || !accent.ok || !background.ok) {
      setError(t('admin.appearance.invalidColor'))
      return
    }
    setSaving(true)
    setError(null)
    setSaveMessage(null)
    try {
      const updated = await patchSalonAppearance(
        session.token,
        session.salon.salon_id,
        {
          colors: {
            primary_color: primary.color,
            accent_soft_color: accent.color,
            background_color: background.color,
          },
        },
      )
      setAppearance(updated)
      setPrimaryInput(updated.primary_color ?? '')
      setAccentInput(updated.accent_soft_color ?? '')
      setBackgroundInput(updated.background_color ?? '')
      setSaveMessage(t('admin.appearance.saved'))
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      setError(adminUserErrorMessage(err, 'admin.appearance.saveFailed'))
    } finally {
      setSaving(false)
    }
  }

  async function handleClearColors() {
    if (!session || !canWrite) {
      return
    }
    setSaving(true)
    setError(null)
    setSaveMessage(null)
    try {
      const updated = await patchSalonAppearance(
        session.token,
        session.salon.salon_id,
        { colors: null },
      )
      setAppearance(updated)
      setPrimaryInput('')
      setAccentInput('')
      setBackgroundInput('')
      setSaveMessage(t('admin.appearance.cleared'))
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      setError(adminUserErrorMessage(err, 'admin.appearance.saveFailed'))
    } finally {
      setSaving(false)
    }
  }

  const publicPath = session?.salon.salon_slug
    ? `/s/${session.salon.salon_slug}`
    : null

  return (
    <AdminLayout>
      <section className="admin-appearance">
        <header className="admin-appearance__header">
          <h1 className="admin-appearance__title">{t('admin.appearance.title')}</h1>
          <p className="admin-appearance__lead">{t('admin.appearance.lead')}</p>
        </header>

        {loading ? (
          <p className="admin-schedule__state" role="status">
            {t('common.loading')}
          </p>
        ) : null}

        {error ? (
          <p
            className="admin-schedule__state admin-schedule__state--error"
            role="alert"
          >
            {error}
          </p>
        ) : null}

        {saveMessage ? (
          <p className="admin-appearance__success" role="status">
            {saveMessage}
          </p>
        ) : null}

        {!loading && appearance ? (
          <>
            <div className="admin-appearance__identity">
              <h2 className="admin-appearance__section-title">
                {t('admin.appearance.identity')}
              </h2>
              <form
                className="admin-appearance__name-form"
                onSubmit={(e) => void handleSaveName(e)}
              >
                <label className="form-field">
                  <span className="form-field__label">
                    {t('admin.appearance.salonName')}
                  </span>
                  <input
                    type="text"
                    className="form-field__input"
                    value={nameInput}
                    maxLength={NAME_MAX_LENGTH}
                    disabled={!canWrite || savingName || loading}
                    onChange={(e) => setNameInput(e.target.value)}
                    autoComplete="organization"
                  />
                </label>
                <p className="admin-appearance__hint">
                  {t('admin.appearance.salonNameHint')}
                </p>
                <div className="admin-appearance__form-actions">
                  <button
                    type="submit"
                    className="btn btn--primary"
                    disabled={!canWrite || savingName || loading}
                  >
                    {savingName
                      ? t('common.saving')
                      : t('admin.appearance.saveName')}
                  </button>
                </div>
              </form>
              <div className="admin-appearance__logo-row">
                {session && logoAttachment ? (
                  <AdminMediaPreview
                    token={session.token}
                    salonId={session.salon.salon_id}
                    mediaId={logoAttachment.mediaId}
                    alt={t('admin.appearance.logoAlt')}
                    className="admin-appearance__logo"
                  />
                ) : (
                  <p className="admin-appearance__hint">
                    {t('admin.appearance.noLogo')}
                  </p>
                )}
                <p className="admin-appearance__hint">
                  {t('admin.appearance.logoHint')}{' '}
                  <Link to="/admin/media">{t('admin.nav.media')}</Link>
                </p>
              </div>
            </div>

            <form className="admin-appearance__form" onSubmit={handleSave}>
              <h2 className="admin-appearance__section-title">
                {t('admin.appearance.colors')}
              </h2>
              <p className="admin-appearance__hint">
                {t('admin.appearance.colorsHint')}
              </p>

              <div className="admin-appearance__presets" role="group">
                <span className="admin-appearance__presets-label">
                  {t('admin.appearance.presets')}
                </span>
                {PRESET_PRIMARY.map((color) => (
                  <button
                    key={color}
                    type="button"
                    className="admin-appearance__swatch"
                    style={{ background: color }}
                    aria-label={t('admin.appearance.applyPreset', { color })}
                    disabled={!canWrite || saving}
                    onClick={() => {
                      setPrimaryInput(color)
                      if (!accentInput.trim()) {
                        setAccentInput('#e8f2ec')
                      }
                      if (!backgroundInput.trim()) {
                        setBackgroundInput('#f4f7f5')
                      }
                    }}
                  />
                ))}
              </div>

              <div className="admin-appearance__color-grid">
                <label className="form-field">
                  <span className="form-field__label">
                    {t('admin.appearance.primaryColor')}
                  </span>
                  <div className="admin-appearance__color-input">
                    <input
                      type="color"
                      value={
                        parseOptionalHexColor(primaryInput).ok &&
                        primaryInput.trim()
                          ? primaryInput.trim()
                          : '#2f6b4f'
                      }
                      disabled={!canWrite || saving}
                      onChange={(e) => setPrimaryInput(e.target.value)}
                      aria-label={t('admin.appearance.primaryColor')}
                    />
                    <input
                      type="text"
                      className="form-field__input"
                      value={primaryInput}
                      disabled={!canWrite || saving}
                      placeholder="#2f6b4f"
                      onChange={(e) => setPrimaryInput(e.target.value)}
                    />
                  </div>
                </label>

                <label className="form-field">
                  <span className="form-field__label">
                    {t('admin.appearance.accentColor')}
                  </span>
                  <div className="admin-appearance__color-input">
                    <input
                      type="color"
                      value={
                        parseOptionalHexColor(accentInput).ok &&
                        accentInput.trim()
                          ? accentInput.trim()
                          : '#e8f2ec'
                      }
                      disabled={!canWrite || saving}
                      onChange={(e) => setAccentInput(e.target.value)}
                      aria-label={t('admin.appearance.accentColor')}
                    />
                    <input
                      type="text"
                      className="form-field__input"
                      value={accentInput}
                      disabled={!canWrite || saving}
                      placeholder="#e8f2ec"
                      onChange={(e) => setAccentInput(e.target.value)}
                    />
                  </div>
                </label>

                <label className="form-field">
                  <span className="form-field__label">
                    {t('admin.appearance.backgroundColor')}
                  </span>
                  <div className="admin-appearance__color-input">
                    <input
                      type="color"
                      value={
                        parseOptionalHexColor(backgroundInput).ok &&
                        backgroundInput.trim()
                          ? backgroundInput.trim()
                          : '#f4f7f5'
                      }
                      disabled={!canWrite || saving}
                      onChange={(e) => setBackgroundInput(e.target.value)}
                      aria-label={t('admin.appearance.backgroundColor')}
                    />
                    <input
                      type="text"
                      className="form-field__input"
                      value={backgroundInput}
                      disabled={!canWrite || saving}
                      placeholder="#f4f7f5"
                      onChange={(e) => setBackgroundInput(e.target.value)}
                    />
                  </div>
                </label>
              </div>

              <div className="admin-appearance__form-actions">
                <button
                  type="submit"
                  className="btn btn--primary"
                  disabled={!canWrite || saving}
                >
                  {saving
                    ? t('common.saving')
                    : t('admin.appearance.save')}
                </button>
                <button
                  type="button"
                  className="btn btn--secondary"
                  disabled={!canWrite || saving}
                  onClick={() => void handleClearColors()}
                >
                  {t('admin.appearance.resetColors')}
                </button>
              </div>
            </form>

            {session ? (
              <div className="admin-appearance__background-media">
                <h2 className="admin-appearance__section-title">
                  {t('admin.appearance.backgroundImage')}
                </h2>
                <p className="admin-appearance__hint">
                  {t('admin.appearance.backgroundImageHint')}
                </p>
                <AdminEntityMediaAttach
                  token={session.token}
                  salonId={session.salon.salon_id}
                  canWrite={canWrite}
                  entityType="salon"
                  entityId={session.salon.salon_id}
                  purpose="cover"
                  label={t('admin.appearance.backgroundImage')}
                  assets={mediaIndex.assets}
                  attachment={coverAttachment}
                  attachmentLoading={mediaIndex.loading}
                  onUpdated={() => void mediaIndex.reload()}
                  onUnauthorized={clearAuthAndRedirect}
                />
              </div>
            ) : null}

            <div className="admin-appearance__preview">
              <h2 className="admin-appearance__section-title">
                {t('admin.appearance.preview')}
              </h2>
              <div
                className="admin-appearance__preview-frame public-salon-page"
                style={previewStyle}
              >
                <p className="admin-appearance__preview-name">
                  {previewName}
                </p>
                <p className="admin-appearance__preview-lead">
                  {t('admin.appearance.previewLead')}
                </p>
                <button type="button" className="btn btn--primary" disabled>
                  {t('admin.appearance.previewCta')}
                </button>
              </div>
              {publicPath ? (
                <p className="admin-appearance__hint">
                  <Link to={publicPath} target="_blank" rel="noreferrer">
                    {t('admin.appearance.openPublic')}
                  </Link>
                </p>
              ) : null}
            </div>
          </>
        ) : null}

        {!canWrite && !loading ? (
          <p className="admin-appearance__hint" role="status">
            {t('admin.appearance.readOnly')}
          </p>
        ) : null}
      </section>
    </AdminLayout>
  )
}
