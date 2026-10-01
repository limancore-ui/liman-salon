import { useCallback, useEffect, useState } from 'react'
import { AdminLayout } from '../components/AdminLayout'
import { useAuth } from '../auth/AuthContext'
import { fetchSalonSettings, patchSalonSettings } from '../api/salonSettings'
import { ApiError } from '../api/errors'
import { isUnauthorizedError } from '../api/auth'
import type { SalonSettings } from '../types/salonSettings'

const MIN_HOLD = 60
const MAX_HOLD = 3600

function canManageSettings(role: string | undefined): boolean {
  return role === 'owner' || role === 'admin'
}

function formatHoldLabel(seconds: number): string {
  const minutes = Math.round(seconds / 60)
  if (seconds % 60 === 0) {
    return `${minutes} min (${seconds}s)`
  }
  return `${seconds}s`
}

export function AdminSalonSettingsPage() {
  const { session, clearAuthAndRedirect } = useAuth()
  const [settings, setSettings] = useState<SalonSettings | null>(null)
  const [holdInput, setHoldInput] = useState('')
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
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError('Could not load salon settings.')
      }
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
      setError(`Hold time must be an integer between ${MIN_HOLD} and ${MAX_HOLD} seconds.`)
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
      setSaveMessage('Settings saved.')
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError('Could not save settings.')
      }
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
      setSaveMessage('Salon override cleared; platform default applies.')
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError('Could not reset settings.')
      }
    } finally {
      setSaving(false)
    }
  }

  const usingOverride = settings?.booking?.public_hold_seconds != null
  const overrideSeconds = settings?.booking?.public_hold_seconds

  return (
    <AdminLayout>
      <section className="admin-schedule">
        <header className="admin-schedule__header">
          <h1 className="admin-schedule__title">Salon settings</h1>
          <p className="admin-schedule__lead">
            Configure per-salon booking behavior. When a hold override is set, pending
            checkout uses that value; otherwise the platform default applies.
          </p>
        </header>

        {loading ? (
          <p className="admin-schedule__state" role="status">
            Loading settings…
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
              <strong>Pending hold:</strong>{' '}
              {usingOverride && overrideSeconds != null
                ? `${formatHoldLabel(overrideSeconds)} (salon override)`
                : 'Platform default (no salon override)'}
            </p>

            {canWrite ? (
              <form className="admin-schedule__form" onSubmit={(e) => void handleSave(e)}>
                <h2 className="admin-schedule__form-title">Public booking hold (seconds)</h2>
                <div className="admin-schedule__form-grid">
                  <label>
                    Hold duration
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
                  Allowed range: {MIN_HOLD}–{MAX_HOLD} seconds (1 minute to 1 hour).
                </p>
                <div className="admin-schedule__form-actions">
                  <button type="submit" className="btn btn--primary" disabled={saving}>
                    {saving ? 'Saving…' : 'Save hold override'}
                  </button>
                  <button
                    type="button"
                    className="btn btn--secondary"
                    disabled={saving || !usingOverride}
                    onClick={() => void handleResetToPlatformDefault()}
                  >
                    Reset to platform default
                  </button>
                </div>
              </form>
            ) : (
              <p className="admin-schedule__lead">
                Only owners and admins can change salon settings.
              </p>
            )}
          </div>
        ) : null}
      </section>
    </AdminLayout>
  )
}
