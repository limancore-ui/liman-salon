import { describe, expect, it } from 'vitest'
import type { StaffListItem } from '../types/staff'
import {
  buildStaffUpdatePatch,
  hasStaffUnsupportedClear,
  parseStaffFormFields,
  staffFormFromRow,
} from './adminStaffForm'

function makeRow(overrides: Partial<StaffListItem> = {}): StaffListItem {
  return {
    id: 'staff-1',
    display_name: 'Alex',
    title: 'Stylist',
    bio: 'Bio text',
    color_hex: '#AABBCC',
    is_bookable: true,
    is_active: true,
    sort_order: 0,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('parseStaffFormFields', () => {
  it('rejects title longer than 100 characters', () => {
    const form = staffFormFromRow(makeRow())
    form.title = 'x'.repeat(101)

    const result = parseStaffFormFields(form)

    expect(result).toBe('Должность не длиннее 100 символов.')
  })

  it('accepts title at 100 characters', () => {
    const form = staffFormFromRow(makeRow())
    form.title = 'x'.repeat(100)

    const result = parseStaffFormFields(form)

    expect(typeof result).toBe('object')
    if (typeof result === 'object') {
      expect(result.title).toHaveLength(100)
    }
  })
})

describe('buildStaffUpdatePatch clearing semantics', () => {
  it('does not send null when user clears title', () => {
    const original = makeRow({ title: 'Stylist' })
    const parsed = parseStaffFormFields({
      ...staffFormFromRow(original),
      title: '',
    })
    expect(typeof parsed).toBe('object')
    if (typeof parsed !== 'object') {
      return
    }

    expect(hasStaffUnsupportedClear(original, parsed)).toBe(true)
    expect(buildStaffUpdatePatch(original, parsed)).toEqual({})
  })

  it('still patches other fields when clear is not attempted', () => {
    const original = makeRow({ title: 'Stylist' })
    const form = staffFormFromRow(original)
    form.displayName = 'Alex R.'
    const parsed = parseStaffFormFields(form)
    expect(typeof parsed).toBe('object')
    if (typeof parsed !== 'object') {
      return
    }

    expect(buildStaffUpdatePatch(original, parsed)).toEqual({
      display_name: 'Alex R.',
    })
  })

  it('allows setting title when original was empty', () => {
    const original = makeRow({ title: null })
    const form = staffFormFromRow(original)
    form.title = 'Lead'
    const parsed = parseStaffFormFields(form)
    expect(typeof parsed).toBe('object')
    if (typeof parsed !== 'object') {
      return
    }

    expect(hasStaffUnsupportedClear(original, parsed)).toBe(false)
    expect(buildStaffUpdatePatch(original, parsed)).toEqual({ title: 'Lead' })
  })
})
