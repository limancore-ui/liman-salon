import { AdminLayout } from '../components/AdminLayout'
import { useAuth } from '../auth/AuthContext'

export function AdminDashboardPage() {
  const { session } = useAuth()
  const salon = session?.salon
  const user = session?.user

  return (
    <AdminLayout>
      <section className="admin-dashboard">
        <h1 className="admin-dashboard__title">Dashboard</h1>
        <p className="admin-dashboard__lead">
          Welcome{user?.full_name ? `, ${user.full_name}` : ''}. Admin modules will
          appear here in later increments.
        </p>
        <dl className="admin-dashboard__meta">
          <div className="admin-dashboard__row">
            <dt>Salon</dt>
            <dd>{salon?.salon_name}</dd>
          </div>
          <div className="admin-dashboard__row">
            <dt>Signed in as</dt>
            <dd>{user?.email}</dd>
          </div>
          <div className="admin-dashboard__row">
            <dt>Role</dt>
            <dd>{salon?.role}</dd>
          </div>
        </dl>
      </section>
    </AdminLayout>
  )
}
