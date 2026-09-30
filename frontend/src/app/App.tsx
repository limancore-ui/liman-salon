import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AdminRoutes } from './AdminRoutes'
import { PublicManageBookingPage } from '../pages/PublicManageBookingPage'
import { PublicSalonPage } from '../pages/PublicSalonPage'

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/s/:slug" element={<PublicSalonPage />} />
        <Route
          path="/s/:slug/bookings/:bookingId/manage"
          element={<PublicManageBookingPage />}
        />
        <Route path="/admin/*" element={<AdminRoutes />} />
        <Route
          path="*"
          element={
            <main className="page">
              <p className="page__hint">
                Open a salon at <code>/s/your-salon-slug</code>
              </p>
            </main>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}
