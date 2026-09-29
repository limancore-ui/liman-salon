/** Matches backend `PublicSalonEntryResponse`. */
export type PublicSalonEntryResponse = {
  salon_id: string
  slug: string
  name: string
  currency_code: string
  timezone: string
  logo_media_id: string | null
}

/** Salon entry with resolved public logo URL when media is attached. */
export type PublicSalonWithMedia = PublicSalonEntryResponse & {
  logo_url: string | null
}

/** Selected availability slot including assignable staff (required for POST). */
export type PublicSelectedSlot = {
  staff_id: string
  service_start: string
  service_end: string
}

/** Sentinel id for “any bookable staff” in staff picker UI state. */
export const ANY_STAFF_CHOICE_ID = '__any_staff__'

export type BookingWizardStep =
  | 'staff'
  | 'date'
  | 'time'
  | 'customer'
  | 'confirmation'
