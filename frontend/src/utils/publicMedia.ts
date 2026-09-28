/** Public inline content URL for a salon media asset (no auth). */
export function publicMediaContentUrl(slug: string, mediaId: string): string {
  return `/api/v1/public/salons/${encodeURIComponent(slug)}/media/${encodeURIComponent(mediaId)}/content`
}

export function resolvePublicMediaUrl(
  slug: string,
  mediaId: string | null | undefined,
): string | null {
  if (!mediaId) {
    return null
  }
  return publicMediaContentUrl(slug, mediaId)
}

/** Authenticated admin content URL (requires Bearer on fetch; not for bare `<img src>`). */
export function adminMediaContentPath(salonId: string, mediaId: string): string {
  return `/api/v1/salons/${encodeURIComponent(salonId)}/media/${encodeURIComponent(mediaId)}/content`
}
