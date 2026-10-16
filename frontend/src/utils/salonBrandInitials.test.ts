import { describe, expect, it } from 'vitest'
import { salonBrandInitials } from './salonBrandInitials'

describe('salonBrandInitials', () => {
  it('uses first letters of two words', () => {
    expect(salonBrandInitials('Malina Beauty')).toBe('MB')
  })

  it('uses up to two characters for a single word', () => {
    expect(salonBrandInitials('Весна')).toBe('ВЕ')
  })

  it('trims whitespace and ignores empty segments', () => {
    expect(salonBrandInitials('  Liman   Salon  ')).toBe('LS')
  })

  it('falls back for empty names', () => {
    expect(salonBrandInitials('')).toBe('?')
    expect(salonBrandInitials('   ')).toBe('?')
  })
})
