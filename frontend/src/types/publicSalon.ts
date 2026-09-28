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
