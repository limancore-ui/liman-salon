import type { CSSProperties } from 'react'
import type { PublicSalonAppearance } from '../types/salonAppearance'

/**
 * Reserved CSS custom properties for per-salon public branding.
 * Defaults live on `.public-salon-page` in `index.css`.
 *
 * Logo remains `SalonHeader` (name + logo_url). Colors and optional cover
 * come from the public salon entry → `hintsFromPublicSalonAppearance`.
 */
export const SALON_THEME_CSS_VARS = {
  accent: '--salon-accent',
  accentSoft: '--salon-accent-soft',
  bg: '--salon-bg',
  bgImage: '--salon-bg-image',
  surface: '--salon-surface',
} as const

/** Optional branding hints from public/admin appearance fields. */
export type SalonPublicThemeHints = {
  primaryColor?: string | null
  accentSoftColor?: string | null
  backgroundColor?: string | null
  backgroundImageUrl?: string | null
  surfaceColor?: string | null
}

export function hintsFromPublicSalonAppearance(
  appearance: PublicSalonAppearance | null | undefined,
  backgroundImageUrl?: string | null,
): SalonPublicThemeHints | null {
  if (
    appearance == null &&
    (backgroundImageUrl == null || backgroundImageUrl === '')
  ) {
    return null
  }
  return {
    primaryColor: appearance?.primary_color ?? null,
    accentSoftColor: appearance?.accent_soft_color ?? null,
    backgroundColor: appearance?.background_color ?? null,
    backgroundImageUrl: backgroundImageUrl ?? null,
  }
}

function isNonEmptyCssValue(value: string | null | undefined): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

/**
 * Builds inline CSS variable overrides for the public salon shell.
 * Returns `undefined` when there is nothing to apply (current production case).
 */
export function buildSalonThemeStyle(
  hints?: SalonPublicThemeHints | null,
): CSSProperties | undefined {
  if (hints == null) {
    return undefined
  }

  const style: Record<string, string> = {}

  if (isNonEmptyCssValue(hints.primaryColor)) {
    style[SALON_THEME_CSS_VARS.accent] = hints.primaryColor.trim()
  }
  if (isNonEmptyCssValue(hints.accentSoftColor)) {
    style[SALON_THEME_CSS_VARS.accentSoft] = hints.accentSoftColor.trim()
  }
  if (isNonEmptyCssValue(hints.backgroundColor)) {
    style[SALON_THEME_CSS_VARS.bg] = hints.backgroundColor.trim()
  }
  if (isNonEmptyCssValue(hints.backgroundImageUrl)) {
    style[SALON_THEME_CSS_VARS.bgImage] =
      `url(${JSON.stringify(hints.backgroundImageUrl.trim())})`
  }
  if (isNonEmptyCssValue(hints.surfaceColor)) {
    style[SALON_THEME_CSS_VARS.surface] = hints.surfaceColor.trim()
  }

  return Object.keys(style).length > 0
    ? (style as CSSProperties)
    : undefined
}
