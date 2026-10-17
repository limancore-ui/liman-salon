import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { t } from '../i18n'

export function AdminNoAccessPage() {
  const { status, pendingWorkspace, logout } = useAuth()

  if (status === 'loading') {
    return (
      <main className="page page--admin-auth">
        <p className="page__hint">{t('admin.noAccess.checking')}</p>
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
        <h1 className="admin-login__title">{t('admin.noAccess.title')}</h1>
        <p className="admin-login__lead">
          {email
            ? t('admin.noAccess.leadWithEmail', { email })
            : t('admin.noAccess.lead')}
        </p>
        <p className="page__hint">{t('admin.noAccess.hint')}</p>
        <button
          type="button"
          className="btn btn--primary btn--block"
          onClick={logout}
        >
          {t('common.logOut')}
        </button>
      </div>
    </main>
  )
}
