import { Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from '../auth/AuthContext'
import { ProtectedAdminRoute } from '../auth/ProtectedAdminRoute'
import { AdminBookingsPage } from '../pages/AdminBookingsPage'
import { AdminStaffPage } from '../pages/AdminStaffPage'
import { AdminServicesPage } from '../pages/AdminServicesPage'
import { AdminCustomersPage } from '../pages/AdminCustomersPage'
import { AdminSchedulePage } from '../pages/AdminSchedulePage'
import { AdminMediaPage } from '../pages/AdminMediaPage'
import { AdminDashboardPage } from '../pages/AdminDashboardPage'
import { AdminSalonSettingsPage } from '../pages/AdminSalonSettingsPage'
import { AdminLoginPage } from '../pages/AdminLoginPage'

export function AdminRoutes() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="login" element={<AdminLoginPage />} />
        <Route element={<ProtectedAdminRoute />}>
          <Route index element={<AdminDashboardPage />} />
          <Route path="bookings" element={<AdminBookingsPage />} />
          <Route path="customers" element={<AdminCustomersPage />} />
          <Route path="staff" element={<AdminStaffPage />} />
          <Route path="services" element={<AdminServicesPage />} />
          <Route path="schedule" element={<AdminSchedulePage />} />
          <Route path="media" element={<AdminMediaPage />} />
          <Route path="settings" element={<AdminSalonSettingsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/admin" replace />} />
      </Routes>
    </AuthProvider>
  )
}
