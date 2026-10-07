import { describe, expect, it } from 'vitest'
import type { CustomerFormState } from '../types/publicBooking'
import {
  isCustomerPhoneLookupEligible,
  validateCustomerForm,
} from './validateCustomerForm'

function form(phone: string): CustomerFormState {
  return { full_name: 'Jane', phone, customer_notes: '' }
}

describe('validateCustomerForm phone', () => {
  it('accepts exactly 9 local digits', () => {
    expect(validateCustomerForm(form('555123456')).phone).toBeUndefined()
  })

  it('requires a phone', () => {
    expect(validateCustomerForm(form('')).phone).toBeDefined()
  })

  it('rejects wrong digit counts and non-digits', () => {
    expect(validateCustomerForm(form('55512345')).phone).toBeDefined()
    expect(validateCustomerForm(form('5551234567')).phone).toBeDefined()
    expect(validateCustomerForm(form('55512345a')).phone).toBeDefined()
    expect(validateCustomerForm(form('+996555123456')).phone).toBeDefined()
  })
})

describe('isCustomerPhoneLookupEligible', () => {
  it('is true only for a complete local number', () => {
    expect(isCustomerPhoneLookupEligible('555123456')).toBe(true)
    expect(isCustomerPhoneLookupEligible('5551234')).toBe(false)
    expect(isCustomerPhoneLookupEligible('')).toBe(false)
  })
})
