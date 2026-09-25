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
