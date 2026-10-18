import { useEffect, useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/errors'
import { useAuth } from '../auth/AuthContext'
import { NoSalonAccessError, SalonContextResolutionError } from '../auth/session'
import { isUnauthorizedError } from '../api/auth'
import { t } from '../i18n'

export function AdminLoginPage() {
  const navigate = useNavigate()
  const { status, login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    if (status === 'authenticated') {
      navigate('/admin', { replace: true })
    } else if (status === 'workspace_picker') {
      navigate('/admin/workspace', { replace: true })
    } else if (status === 'no_salon_access') {
      navigate('/admin/no-access', { replace: true })
    }
  }, [status, navigate])

  if (status === 'loading') {
    return (
      <main className="page page--admin-auth">
        <p className="page__hint">{t('admin.login.checking')}</p>
      </main>
    )
  }

  if (status === 'authenticated') {
    return <Navigate to="/admin" replace />
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErrorMessage(null)
    setSubmitting(true)
    try {
      await login(email.trim(), password)
    } catch (error) {
      if (error instanceof NoSalonAccessError) {
        navigate('/admin/no-access', { replace: true })
        return
      }
      if (error instanceof ApiError && error.status === 401) {
        setErrorMessage(t('admin.login.invalidCredentials'))
      } else if (error instanceof SalonContextResolutionError) {
        setErrorMessage(error.message)
      } else if (isUnauthorizedError(error)) {
        setErrorMessage(t('admin.login.invalidCredentials'))
      } else if (error instanceof ApiError && error.status === 0) {
        setErrorMessage(t('common.networkError'))
      } else {
        setErrorMessage(t('admin.login.failed'))
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="page page--admin-auth">
      <div className="admin-login">
        <h1 className="admin-login__title">{t('admin.login.title')}</h1>
        <p className="admin-login__lead">{t('admin.login.lead')}</p>
        <form className="admin-login__form" onSubmit={handleSubmit}>
          {errorMessage ? (
            <div className="form-error-banner" role="alert">
              <p>{errorMessage}</p>
            </div>
          ) : null}
          <div className="form-field">
            <label className="form-field__label" htmlFor="admin-email">
              {t('admin.login.email')}
            </label>
            <input
              id="admin-email"
              className="form-field__input"
              type="email"
              name="email"
              autoComplete="username"
              required
              value={email}
              disabled={submitting}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <div className="form-field">
            <label className="form-field__label" htmlFor="admin-password">
              {t('admin.login.password')}
            </label>
            <input
              id="admin-password"
              className="form-field__input"
              type="password"
              name="password"
              autoComplete="current-password"
              required
              value={password}
              disabled={submitting}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
          <button
            type="submit"
            className="btn btn--primary btn--block"
            disabled={submitting}
          >
            {submitting ? t('admin.login.submitting') : t('admin.login.submit')}
          </button>
        </form>
      </div>
    </main>
  )
}
