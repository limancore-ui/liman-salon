/** Matches backend `PublicBookingOrchestrateRequest` (client payload only). */
export type PublicBookingCreatePayload = {
  phone: string
  full_name: string
  email?: string | null
  service_id: string
  staff_id: string
  service_start: string
  customer_notes?: string | null
}

/** Matches backend `PublicBookingOrchestrateResponse`. */
export type PublicBookingCreateResponse = {
  salon_id: string
  customer_id: string
  booking_id: string
  service_start: string
  service_end: string
  hold_expires_at: string
  manage_token: string
}

/** Matches backend `PublicBookingCancelRequest`. */
export type PublicBookingCancelRequest = {
  token: string
  reason?: string | null
}

/** Matches backend `PublicBookingCancelResponse`. */
export type PublicBookingCancelResponse = {
  booking_id: string
  status: string
  cancelled_at: string
}

/** Matches backend `PublicBookingRescheduleRequest`. */
export type PublicBookingRescheduleRequest = {
  token: string
  staff_id: string
  service_start: string
}

/** Matches backend `PublicBookingRescheduleResponse`. */
export type PublicBookingRescheduleResponse = {
  booking_id: string
  status: string
  staff_id: string
  service_start: string
  service_end: string
}

/** Client-side session snapshot for manage/cancel/reschedule (not from backend). */
export type ManageBookingSnapshot = {
  token: string
  booking_id: string
  slug: string
  salon_id: string
  service_id: string
  staff_id: string
  service_name: string
  staff_display_name: string
  service_start: string
  service_end: string
  hold_expires_at: string
  status?: string
  cancelled_at?: string
}

export type CustomerFormState = {
  full_name: string
  phone: string
  customer_notes: string
}

export type CustomerFormFieldErrors = Partial<
  Record<keyof CustomerFormState, string>
>

export const EMPTY_CUSTOMER_FORM: CustomerFormState = {
  full_name: '',
  phone: '',
  customer_notes: '',
}
