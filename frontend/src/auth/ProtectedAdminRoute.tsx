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

  if (status !== 'authenticated') {
    return <Navigate to="/admin/login" replace />
  }

  return <Outlet />
}
