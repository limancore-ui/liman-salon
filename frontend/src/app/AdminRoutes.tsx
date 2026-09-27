import { Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from '../auth/AuthContext'
import { ProtectedAdminRoute } from '../auth/ProtectedAdminRoute'
import { AdminBookingsPage } from '../pages/AdminBookingsPage'
import { AdminStaffPage } from '../pages/AdminStaffPage'
import { AdminServicesPage } from '../pages/AdminServicesPage'
import { AdminDashboardPage } from '../pages/AdminDashboardPage'
import { AdminLoginPage } from '../pages/AdminLoginPage'

export function AdminRoutes() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="login" element={<AdminLoginPage />} />
        <Route element={<ProtectedAdminRoute />}>
          <Route index element={<AdminDashboardPage />} />
          <Route path="bookings" element={<AdminBookingsPage />} />
          <Route path="staff" element={<AdminStaffPage />} />
          <Route path="services" element={<AdminServicesPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/admin" replace />} />
      </Routes>
    </AuthProvider>
  )
}
