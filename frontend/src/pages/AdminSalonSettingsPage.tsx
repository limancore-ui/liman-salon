import { useCallback, useEffect, useState } from 'react'
import { AdminLayout } from '../components/AdminLayout'
import { useAuth } from '../auth/AuthContext'
import { fetchSalonSettings, patchSalonSettings } from '../api/salonSettings'
import { isUnauthorizedError } from '../api/auth'
import { adminUserErrorMessage } from '../utils/adminUserError'
import type { SalonSettings } from '../types/salonSettings'
import { t } from '../i18n'

const MIN_HOLD = 60
const MAX_HOLD = 3600

function canManageSettings(role: string | undefined): boolean {
  return role === 'owner' || role === 'admin'
}

function formatHoldLabel(seconds: number): string {
  const minutes = Math.round(seconds / 60)
  if (seconds % 60 === 0) {
    return t('admin.settings.holdLabelMin', { minutes, seconds })
  }
  return t('admin.settings.holdLabelSec', { seconds })
}

export function AdminSalonSettingsPage() {
  const { session, clearAuthAndRedirect } = useAuth()
  const [settings, setSettings] = useState<SalonSettings | null>(null)
  const [holdInput, setHoldInput] = useState('')
  const [bonusesEnabled, setBonusesEnabled] = useState(false)
  const [earnPercentageInput, setEarnPercentageInput] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)

  const canWrite = canManageSettings(session?.salon.role)

  const load = useCallback(async () => {
    if (!session) {
      return
    }
    setLoading(true)
    setError(null)
    setSaveMessage(null)
    try {
      const data = await fetchSalonSettings(session.token, session.salon.salon_id)
      setSettings(data)
      setHoldInput(
        data.booking?.public_hold_seconds != null
          ? String(data.booking.public_hold_seconds)
          : '',
      )
      setBonusesEnabled(data.bonuses?.enabled ?? false)
      setEarnPercentageInput(
        data.bonuses?.earn_percentage != null ? String(data.bonuses.earn_percentage) : '',
      )
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      setError(adminUserErrorMessage(err, 'admin.settings.loadFailed'))
      setSettings(null)
    } finally {
      setLoading(false)
    }
  }, [session, clearAuthAndRedirect])

  useEffect(() => {
    void load()
  }, [load])

  async function handleSave(event: React.FormEvent) {
    event.preventDefault()
    if (!session || !canWrite) {
      return
    }
    const parsed = Number(holdInput)
    if (!Number.isInteger(parsed) || parsed < MIN_HOLD || parsed > MAX_HOLD) {
      setError(t('admin.settings.holdInvalid', { min: MIN_HOLD, max: MAX_HOLD }))
      return
    }
    setSaving(true)
    setError(null)
    setSaveMessage(null)
    try {
      const updated = await patchSalonSettings(session.token, session.salon.salon_id, {
        booking: { public_hold_seconds: parsed },
      })
      setSettings(updated)
      setHoldInput(String(updated.booking!.public_hold_seconds))
      setSaveMessage(t('admin.settings.saved'))
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      setError(adminUserErrorMessage(err, 'admin.settings.saveFailed'))
    } finally {
      setSaving(false)
    }
  }

  async function handleSaveBonuses(event: React.FormEvent) {
    event.preventDefault()
    if (!session || !canWrite) {
      return
    }
    const parsedPct = Number(earnPercentageInput)
    if (!Number.isFinite(parsedPct) || parsedPct < 0) {
      setError('Процент начисления должен быть неотрицательным числом.')
      return
    }
    setSaving(true)
    setError(null)
    setSaveMessage(null)
    try {
      const updated = await patchSalonSettings(session.token, session.salon.salon_id, {
        bonuses: { enabled: bonusesEnabled, earn_percentage: parsedPct },
      })
      setSettings(updated)
      setBonusesEnabled(updated.bonuses?.enabled ?? false)
      setEarnPercentageInput(
        updated.bonuses?.earn_percentage != null
          ? String(updated.bonuses.earn_percentage)
          : '',
      )
      setSaveMessage(t('admin.settings.saved'))
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      setError(adminUserErrorMessage(err, 'admin.settings.saveFailed'))
    } finally {
      setSaving(false)
    }
  }

  async function handleResetBonuses() {
    if (!session || !canWrite) {
      return
    }
    setSaving(true)
    setError(null)
    setSaveMessage(null)
    try {
      const updated = await patchSalonSettings(session.token, session.salon.salon_id, {
        bonuses: null,
      })
      setSettings(updated)
      setBonusesEnabled(false)
      setEarnPercentageInput('')
      setSaveMessage('Бонусные настройки сброшены (программа выключена по умолчанию).')
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      setError(adminUserErrorMessage(err, 'admin.settings.resetFailed'))
    } finally {
      setSaving(false)
    }
  }

  async function handleResetToPlatformDefault() {
    if (!session || !canWrite) {
      return
    }
    setSaving(true)
    setError(null)
    setSaveMessage(null)
    try {
      const updated = await patchSalonSettings(session.token, session.salon.salon_id, {
        booking: null,
      })
      setSettings(updated)
      setHoldInput('')
      setSaveMessage(t('admin.settings.overrideCleared'))
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      setError(adminUserErrorMessage(err, 'admin.settings.resetFailed'))
    } finally {
      setSaving(false)
    }
  }

  const usingOverride = settings?.booking?.public_hold_seconds != null
  const overrideSeconds = settings?.booking?.public_hold_seconds
  const usingBonusesConfig = settings?.bonuses != null

  return (
    <AdminLayout>
      <section className="admin-schedule">
        <header className="admin-schedule__header">
          <h1 className="admin-schedule__title">{t('admin.settings.title')}</h1>
          <p className="admin-schedule__lead">
            {t('admin.settings.lead')}
          </p>
        </header>

        {loading ? (
          <p className="admin-schedule__state" role="status">
            {t('admin.settings.loading')}
          </p>
        ) : null}

        {error ? (
          <p className="admin-schedule__state admin-schedule__state--error" role="alert">
            {error}
          </p>
        ) : null}

        {saveMessage ? (
          <p className="admin-schedule__state" role="status">
            {saveMessage}
          </p>
        ) : null}

        {settings && !loading ? (
          <div className="admin-schedule__section">
            <p className="admin-schedule__lead">
              <strong>{t('admin.settings.pendingHold')}</strong>{' '}
              {usingOverride && overrideSeconds != null
                ? `${formatHoldLabel(overrideSeconds)} ${t('admin.settings.salonOverride')}`
                : t('admin.settings.platformDefault')}
            </p>

            {canWrite ? (
              <form className="admin-schedule__form" onSubmit={(e) => void handleSave(e)}>
                <h2 className="admin-schedule__form-title">{t('admin.settings.holdTitle')}</h2>
                <div className="admin-schedule__form-grid">
                  <label>
                    {t('admin.settings.holdDuration')}
                    <input
                      type="number"
                      min={MIN_HOLD}
                      max={MAX_HOLD}
                      step={1}
                      value={holdInput}
                      onChange={(e) => setHoldInput(e.target.value)}
                      disabled={saving}
                      required
                    />
                  </label>
                </div>
                <p className="admin-schedule__lead">
                  {t('admin.settings.holdRange', { min: MIN_HOLD, max: MAX_HOLD })}
                </p>
                <div className="admin-schedule__form-actions">
                  <button type="submit" className="btn btn--primary" disabled={saving}>
                    {saving ? t('common.saving') : t('admin.settings.saveHold')}
                  </button>
                  <button
                    type="button"
                    className="btn btn--secondary"
                    disabled={saving || !usingOverride}
                    onClick={() => void handleResetToPlatformDefault()}
                  >
                    {t('admin.settings.resetPlatform')}
                  </button>
                </div>
              </form>
            ) : (
              <p className="admin-schedule__lead">
                {t('admin.settings.readonly')}
              </p>
            )}

            <div className="admin-schedule__section">
              <h2 className="admin-schedule__form-title">Бонусная программа</h2>
              <p className="admin-schedule__lead">
                {usingBonusesConfig
                  ? bonusesEnabled
                    ? `Начисление: ${settings!.bonuses!.earn_percentage}%`
                    : 'Бонусы сохранены, но выключены.'
                  : 'По умолчанию бонусы выключены (настройки не заданы).'}
              </p>
              {canWrite ? (
                <form
                  className="admin-schedule__form"
                  onSubmit={(e) => void handleSaveBonuses(e)}
                >
                  <div className="admin-schedule__form-grid">
                    <label>
                      <input
                        type="checkbox"
                        checked={bonusesEnabled}
                        onChange={(e) => setBonusesEnabled(e.target.checked)}
                        disabled={saving}
                      />{' '}
                      Включить бонусы
                    </label>
                    <label>
                      Процент начисления
                      <input
                        type="number"
                        min={0}
                        step={0.1}
                        value={earnPercentageInput}
                        onChange={(e) => setEarnPercentageInput(e.target.value)}
                        disabled={saving}
                        required
                      />
                    </label>
                  </div>
                  <div className="admin-schedule__form-actions">
                    <button type="submit" className="btn btn--primary" disabled={saving}>
                      {saving ? t('common.saving') : t('admin.settings.saveBonuses')}
                    </button>
                    <button
                      type="button"
                      className="btn btn--secondary"
                      disabled={saving || !usingBonusesConfig}
                      onClick={() => void handleResetBonuses()}
                    >
                      Сбросить бонусы
                    </button>
                  </div>
                </form>
              ) : null}
            </div>
          </div>
        ) : null}
      </section>
    </AdminLayout>
  )
}
