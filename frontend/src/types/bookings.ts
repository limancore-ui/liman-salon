export type BookingListItem = {
  id: string
  status: string
  starts_at: string
  ends_at: string
  duration_minutes: number
  price_cents: number
  customer_name: string
  customer_phone: string | null
  staff_name: string
  service_name: string
  source: string
  created_at: string
}

export type ListBookingsParams = {
  starts_at_from?: string
  starts_at_to?: string
  status?: string
  limit?: number
  offset?: number
}

export type AdminBookingCancelRequest = {
  reason?: string
}

export type AdminBookingCancelResponse = {
  booking_id: string
  status: string
  cancelled_at: string
}

export type AdminBookingRescheduleRequest = {
  staff_id: string
  service_start: string
}

export type AdminBookingRescheduleResponse = {
  booking_id: string
  status: string
  staff_id: string
  service_start: string
  service_end: string
}
