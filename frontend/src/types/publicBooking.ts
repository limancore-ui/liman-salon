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
}

export type CustomerFormState = {
  full_name: string
  phone: string
  email: string
  customer_notes: string
}

export type CustomerFormFieldErrors = Partial<
  Record<keyof CustomerFormState, string>
>

export const EMPTY_CUSTOMER_FORM: CustomerFormState = {
  full_name: '',
  phone: '',
  email: '',
  customer_notes: '',
}
