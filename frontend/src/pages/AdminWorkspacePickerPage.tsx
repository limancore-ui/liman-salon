import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/errors'
import { useAuth } from '../auth/AuthContext'
import { SalonContextResolutionError } from '../auth/session'
import { membershipLabel } from '../auth/workspace'

export function AdminWorkspacePickerPage() {
  const navigate = useNavigate()
  const { status, pendingWorkspace, selectWorkspace, logout } = useAuth()
  const [salonId, setSalonId] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  if (status === 'loading') {
    return (
      <main className="page page--admin-auth">
        <p className="page__hint">Loading workspaces…</p>
      </main>
    )
  }

  if (status === 'authenticated') {
    return <Navigate to="/admin" replace />
  }

  if (status !== 'workspace_picker' || !pendingWorkspace) {
    return <Navigate to="/admin/login" replace />
  }

  const salons = pendingWorkspace.salons

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!salonId) {
      setErrorMessage('Choose a salon workspace.')
      return
    }
    setErrorMessage(null)
    setSubmitting(true)
    try {
      await selectWorkspace(salonId)
      navigate('/admin', { replace: true })
    } catch (error) {
      if (error instanceof SalonContextResolutionError) {
        setErrorMessage(error.message)
      } else if (error instanceof ApiError && error.status === 0) {
        setErrorMessage('Network error. Try again.')
      } else {
        setErrorMessage('Could not open that workspace. Try again.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="page page--admin-auth">
      <div className="admin-login">
        <h1 className="admin-login__title">Choose workspace</h1>
        <p className="admin-login__lead">
          Signed in as {pendingWorkspace.user.email}. Select a salon to manage.
        </p>
        <form className="admin-login__form" onSubmit={handleSubmit}>
          {errorMessage ? (
            <div className="form-error-banner" role="alert">
              <p>{errorMessage}</p>
            </div>
          ) : null}
          <div className="form-field">
            <label className="form-field__label" htmlFor="admin-workspace">
              Salon
            </label>
            <select
              id="admin-workspace"
              className="form-field__input"
              value={salonId}
              disabled={submitting}
              onChange={(event) => setSalonId(event.target.value)}
              required
            >
              <option value="">Select a salon…</option>
              {salons.map((membership) => (
                <option key={membership.salon_id} value={membership.salon_id}>
                  {membershipLabel(membership)} — {membership.role}
                </option>
              ))}
            </select>
          </div>
          <button
            type="submit"
            className="btn btn--primary btn--block"
            disabled={submitting}
          >
            {submitting ? 'Opening…' : 'Continue'}
          </button>
          <button
            type="button"
            className="btn btn--secondary btn--block"
            disabled={submitting}
            onClick={logout}
          >
            Log out
          </button>
        </form>
      </div>
    </main>
  )
}
