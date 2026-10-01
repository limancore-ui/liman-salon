import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export function AdminNoAccessPage() {
  const { status, pendingWorkspace, logout } = useAuth()

  if (status === 'loading') {
    return (
      <main className="page page--admin-auth">
        <p className="page__hint">Checking access…</p>
      </main>
    )
  }

  if (status === 'authenticated') {
    return <Navigate to="/admin" replace />
  }

  if (status !== 'no_salon_access') {
    return <Navigate to="/admin/login" replace />
  }

  const email = pendingWorkspace?.user.email

  return (
    <main className="page page--admin-auth">
      <div className="admin-login">
        <h1 className="admin-login__title">No salon access</h1>
        <p className="admin-login__lead">
          {email
            ? `${email} is not linked to any active salon workspace.`
            : 'Your account is not linked to any active salon workspace.'}
        </p>
        <p className="page__hint">
          Ask a salon owner or administrator to invite you, then sign in again.
        </p>
        <button
          type="button"
          className="btn btn--primary btn--block"
          onClick={logout}
        >
          Log out
        </button>
      </div>
    </main>
  )
}
