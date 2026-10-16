/**
 * @vitest-environment node
 */
import { describe, expect, it } from 'vitest'
import {
  isValidHexColor,
  parseOptionalHexColor,
} from './salonAppearanceColors'

describe('salonAppearanceColors', () => {
  it('accepts #RRGGBB and rejects unsafe values', () => {
    expect(isValidHexColor('#2f6b4f')).toBe(true)
    expect(isValidHexColor('#ABCDEF')).toBe(true)
    expect(isValidHexColor('red')).toBe(false)
    expect(isValidHexColor('url(https://x)')).toBe(false)
    expect(isValidHexColor('#fff')).toBe(false)
  })

  it('parses empty as clear and invalid as failure', () => {
    expect(parseOptionalHexColor('')).toEqual({ ok: true, color: null })
    expect(parseOptionalHexColor('  ')).toEqual({ ok: true, color: null })
    expect(parseOptionalHexColor('#AaBbCc')).toEqual({
      ok: true,
      color: '#aabbcc',
    })
    expect(parseOptionalHexColor('javascript:alert(1)')).toEqual({ ok: false })
  })
})
