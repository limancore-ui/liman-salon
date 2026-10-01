import { Navigate, Outlet } from 'react-router-dom'
import { LoadingState } from '../components/LoadingState'
import { useAuth } from './AuthContext'

export function ProtectedAdminRoute() {
  const { status } = useAuth()

  if (status === 'loading') {
    return (
      <main className="page">
        <LoadingState message="Checking sign-in…" />
      </main>
    )
  }

  if (status === 'workspace_picker') {
    return <Navigate to="/admin/workspace" replace />
  }

  if (status === 'no_salon_access') {
    return <Navigate to="/admin/no-access" replace />
  }

  if (status !== 'authenticated') {
    return <Navigate to="/admin/login" replace />
  }

  return <Outlet />
}
