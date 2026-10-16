/** Matches backend `SalonProfileResponse`. */
export type SalonProfile = {
  salon_id: string
  name: string
  slug: string
}

/** Matches backend `SalonProfilePatchRequest`. */
export type SalonProfilePatch = {
  name: string
}
