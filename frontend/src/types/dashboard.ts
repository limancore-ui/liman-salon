export type DashboardStatusCounts = {
  pending: number
  confirmed: number
  in_progress: number
  completed: number
  cancelled: number
  no_show: number
  expired: number
}

export type DashboardUpcomingBooking = {
  id: string
  starts_at: string
  ends_at: string
  customer_name: string
  customer_phone: string | null
  service_name: string
  staff_name: string
  status: string
  price_cents: number
}

export type DashboardWarning = {
  code: string
  count: number | null
}

export type AdminDashboardSnapshot = {
  salon_date: string
  today_booking_count: number
  status_counts: DashboardStatusCounts
  upcoming_bookings: DashboardUpcomingBooking[]
  active_staff_count: number
  warnings: DashboardWarning[]
}
