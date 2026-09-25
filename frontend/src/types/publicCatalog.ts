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
}

/** Matches backend `PublicCatalogStaffResponse`. */
export type PublicCatalogStaffResponse = {
  salon_id: string
  service_id: string
  staff: PublicCatalogStaffOut[]
}
