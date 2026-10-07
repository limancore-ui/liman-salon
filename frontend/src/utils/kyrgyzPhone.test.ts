import { describe, expect, it } from 'vitest'
import {
  isCompleteKgLocalPhone,
  sanitizeKgLocalPhone,
  toCanonicalKgPhone,
} from './kyrgyzPhone'

describe('sanitizeKgLocalPhone', () => {
  it('keeps digits only', () => {
    expect(sanitizeKgLocalPhone('555 12-34a56')).toBe('555123456')
  })

  it('caps at 9 digits', () => {
    expect(sanitizeKgLocalPhone('5551234567890')).toBe('555123456')
  })

  it('strips a pasted +996 prefix', () => {
    expect(sanitizeKgLocalPhone('+996 555 123 456')).toBe('555123456')
    expect(sanitizeKgLocalPhone('996555123456')).toBe('555123456')
  })

  it('does not strip while the user is still typing short values', () => {
    expect(sanitizeKgLocalPhone('996')).toBe('996')
    expect(sanitizeKgLocalPhone('99655')).toBe('99655')
  })
})

describe('isCompleteKgLocalPhone', () => {
  it('requires exactly 9 digits', () => {
    expect(isCompleteKgLocalPhone('555123456')).toBe(true)
    expect(isCompleteKgLocalPhone('55512345')).toBe(false)
    expect(isCompleteKgLocalPhone('5551234567')).toBe(false)
    expect(isCompleteKgLocalPhone('55512345a')).toBe(false)
    expect(isCompleteKgLocalPhone('')).toBe(false)
  })
})

describe('toCanonicalKgPhone', () => {
  it('prefixes +996', () => {
    expect(toCanonicalKgPhone('555123456')).toBe('+996555123456')
  })
})
