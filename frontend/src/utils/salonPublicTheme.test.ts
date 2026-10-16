/**
 * @vitest-environment node
 */
import { describe, expect, it } from 'vitest'
import {
  SALON_THEME_CSS_VARS,
  buildSalonThemeStyle,
  hintsFromPublicSalonAppearance,
} from './salonPublicTheme'

describe('hintsFromPublicSalonAppearance', () => {
  it('returns null when no appearance and no background image', () => {
    expect(hintsFromPublicSalonAppearance(null)).toBeNull()
    expect(hintsFromPublicSalonAppearance(undefined, null)).toBeNull()
  })

  it('maps public appearance fields for theme style', () => {
    expect(
      hintsFromPublicSalonAppearance(
        {
          primary_color: '#1e4d7b',
          accent_soft_color: '#e3eef8',
          background_color: '#f5f7fa',
        },
        '/api/cover',
      ),
    ).toEqual({
      primaryColor: '#1e4d7b',
      accentSoftColor: '#e3eef8',
      backgroundColor: '#f5f7fa',
      backgroundImageUrl: '/api/cover',
    })
  })
})

describe('buildSalonThemeStyle', () => {
  it('returns undefined when hints are missing or empty', () => {
    expect(buildSalonThemeStyle()).toBeUndefined()
    expect(buildSalonThemeStyle(null)).toBeUndefined()
    expect(buildSalonThemeStyle({})).toBeUndefined()
    expect(
      buildSalonThemeStyle({
        primaryColor: '  ',
        backgroundImageUrl: null,
      }),
    ).toBeUndefined()
  })

  it('maps non-empty branding hints onto reserved CSS variables', () => {
    const style = buildSalonThemeStyle({
      primaryColor: '#2f6b4f',
      accentSoftColor: '#e8f2ec',
      backgroundColor: '#f4f7f5',
      backgroundImageUrl: 'https://cdn.example/cover.jpg',
      surfaceColor: '#ffffff',
    })

    expect(style).toEqual({
      [SALON_THEME_CSS_VARS.accent]: '#2f6b4f',
      [SALON_THEME_CSS_VARS.accentSoft]: '#e8f2ec',
      [SALON_THEME_CSS_VARS.bg]: '#f4f7f5',
      [SALON_THEME_CSS_VARS.bgImage]: 'url("https://cdn.example/cover.jpg")',
      [SALON_THEME_CSS_VARS.surface]: '#ffffff',
    })
  })
})
