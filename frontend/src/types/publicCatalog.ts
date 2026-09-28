/** Matches backend `PublicCatalogServiceOut`. */
export type PublicCatalogServiceOut = {
  id: string
  name: string
  description: string | null
  duration_minutes: number
  buffer_before_minutes: number
  buffer_after_minutes: number
  price_cents: number
  currency_code: string
  cover_media_id: string | null
}

export type PublicCatalogServiceWithMedia = PublicCatalogServiceOut & {
  cover_url: string | null
}

/** Matches backend `PublicCatalogServicesResponse`. */
export type PublicCatalogServicesResponse = {
  salon_id: string
  services: PublicCatalogServiceOut[]
}

/** Matches backend `PublicCatalogStaffOut`. */
export type PublicCatalogStaffOut = {
  id: string
  display_name: string
  avatar_media_id: string | null
}

export type PublicCatalogStaffWithMedia = PublicCatalogStaffOut & {
  avatar_url: string | null
}

/** Matches backend `PublicCatalogStaffResponse`. */
export type PublicCatalogStaffResponse = {
  salon_id: string
  service_id: string
  staff: PublicCatalogStaffOut[]
}

/** Matches backend `ServiceAvailabilitySlotOut`. */
export type ServiceAvailabilitySlotOut = {
  service_start: string
  service_end: string
}

/** Matches backend `StaffServiceAvailabilityOut`. */
export type StaffServiceAvailabilityOut = {
  staff_id: string
  slots: ServiceAvailabilitySlotOut[]
}

/** Matches backend `ServiceAvailabilityResponse`. */
export type ServiceAvailabilityResponse = {
  service_id: string
  staff: StaffServiceAvailabilityOut[]
}
