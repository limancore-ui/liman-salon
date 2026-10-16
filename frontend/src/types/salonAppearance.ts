/** Matches backend `SalonAppearanceResponse`. */
export type SalonAppearance = {
  salon_id: string
  salon_name: string
  primary_color?: string | null
  accent_soft_color?: string | null
  background_color?: string | null
  logo_media_id?: string | null
  background_media_id?: string | null
}

/** Matches backend `SalonAppearancePatchRequest`. */
export type SalonAppearancePatch = {
  colors?: {
    primary_color?: string | null
    accent_soft_color?: string | null
    background_color?: string | null
  } | null
}

/** Matches backend `PublicSalonAppearanceResponse`. */
export type PublicSalonAppearance = {
  primary_color?: string | null
  accent_soft_color?: string | null
  background_color?: string | null
}
