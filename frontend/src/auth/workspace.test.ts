import { describe, expect, it } from 'vitest'
import {
  isSalonIdInMemberships,
  membershipLabel,
  resolveSalonSelection,
} from './workspace'
import type { MySalonMembership } from '../types/auth'

const salonA: MySalonMembership = {
  salon_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  salon_name: 'Alpha',
  salon_slug: 'alpha',
  role: 'owner',
}

const salonB: MySalonMembership = {
  salon_id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  salon_name: 'Beta',
  salon_slug: 'beta',
  role: 'staff',
}

describe('resolveSalonSelection', () => {
  it('returns none for zero memberships', () => {
    expect(resolveSalonSelection([], null)).toEqual({ kind: 'none' })
    expect(resolveSalonSelection([], salonA.salon_id)).toEqual({ kind: 'none' })
  })

  it('auto-selects the only membership', () => {
    expect(resolveSalonSelection([salonA], null)).toEqual({
      kind: 'selected',
      salonId: salonA.salon_id,
    })
  })

  it('uses valid hint when multiple salons', () => {
    expect(resolveSalonSelection([salonA, salonB], salonB.salon_id)).toEqual({
      kind: 'selected',
      salonId: salonB.salon_id,
    })
  })

  it('requires picker when hint is missing or stale', () => {
    expect(resolveSalonSelection([salonA, salonB], null)).toEqual({
      kind: 'picker',
    })
    expect(resolveSalonSelection([salonA, salonB], 'stale-id')).toEqual({
      kind: 'picker',
    })
  })
})

describe('isSalonIdInMemberships', () => {
  it('matches membership salon ids', () => {
    expect(isSalonIdInMemberships(salonA.salon_id, [salonA, salonB])).toBe(true)
    expect(isSalonIdInMemberships('missing', [salonA])).toBe(false)
  })
})

describe('membershipLabel', () => {
  it('formats name and slug', () => {
    expect(membershipLabel(salonA)).toBe('Alpha (alpha)')
  })
})
