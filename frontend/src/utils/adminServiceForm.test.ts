import { describe, expect, it } from 'vitest'
import { ApiError } from '../api/errors'
import {
  buildServiceUpdatePatch,
  mapAdminServiceCreateError,
  mapAdminServiceUpdateError,
  serviceActiveToggleLabel,
  serviceActiveTogglePatch,
  serviceFormFromRow,
} from './adminServiceForm'
import type { ServiceListItem } from '../types/services'

const baseRow: ServiceListItem = {
  id: 'svc-1',
  name: 'Cut',
  description: 'Standard cut',
  duration_minutes: 45,
  buffer_before_minutes: 5,
  buffer_after_minutes: 10,
  price_cents: 2500,
  is_active: true,
  sort_order: 1,
  currency_code: 'USD',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('serviceFormFromRow', () => {
  it('pre-fills form strings from service row', () => {
    expect(serviceFormFromRow(baseRow)).toEqual({
      name: 'Cut',
      description: 'Standard cut',
      durationMinutes: '45',
      priceMajor: '25',
      bufferBefore: '5',
      bufferAfter: '10',
      sortOrder: '1',
    })
  })

  it('maps null description to empty string', () => {
    expect(serviceFormFromRow({ ...baseRow, description: null }).description).toBe('')
  })
})

describe('buildServiceUpdatePatch', () => {
  it('returns empty object when nothing changed', () => {
    const parsed = {
      name: baseRow.name,
      description: baseRow.description,
      duration_minutes: baseRow.duration_minutes,
      price_cents: baseRow.price_cents,
      buffer_before_minutes: baseRow.buffer_before_minutes,
      buffer_after_minutes: baseRow.buffer_after_minutes,
      sort_order: baseRow.sort_order,
    }
    expect(buildServiceUpdatePatch(baseRow, parsed)).toEqual({})
  })

  it('includes only changed scalar fields', () => {
    const patch = buildServiceUpdatePatch(baseRow, {
      name: 'Trim',
      description: baseRow.description,
      duration_minutes: 60,
      price_cents: 3000,
      buffer_before_minutes: baseRow.buffer_before_minutes,
      buffer_after_minutes: baseRow.buffer_after_minutes,
      sort_order: baseRow.sort_order,
    })
    expect(patch).toEqual({
      name: 'Trim',
      duration_minutes: 60,
      price_cents: 3000,
    })
  })

  it('can set description to null when cleared', () => {
    const patch = buildServiceUpdatePatch(baseRow, {
      name: baseRow.name,
      description: null,
      duration_minutes: baseRow.duration_minutes,
      price_cents: baseRow.price_cents,
      buffer_before_minutes: baseRow.buffer_before_minutes,
      buffer_after_minutes: baseRow.buffer_after_minutes,
      sort_order: baseRow.sort_order,
    })
    expect(patch).toEqual({ description: null })
  })
})

describe('serviceActiveTogglePatch', () => {
  it('flips is_active only', () => {
    expect(serviceActiveTogglePatch(true)).toEqual({ is_active: false })
    expect(serviceActiveTogglePatch(false)).toEqual({ is_active: true })
  })
})

describe('serviceActiveToggleLabel', () => {
  it('shows Deactivate for active rows and Activate for inactive', () => {
    expect(serviceActiveToggleLabel(true)).toBe('Deactivate')
    expect(serviceActiveToggleLabel(false)).toBe('Activate')
  })
})

describe('mapAdminServiceUpdateError', () => {
  it('maps 403, 422 detail, network, and generic failures', () => {
    expect(mapAdminServiceUpdateError(new ApiError(403, 'Forbidden'))).toBe(
      'You do not have permission to update services.',
    )
    expect(mapAdminServiceUpdateError(new ApiError(422, 'name already taken'))).toBe(
      'name already taken',
    )
    expect(mapAdminServiceUpdateError(new ApiError(0, ''))).toBe(
      'Could not reach the server. Check your connection and try again.',
    )
    expect(mapAdminServiceUpdateError(new ApiError(500, 'x'))).toBe(
      'Could not update the service. Try again later.',
    )
    expect(mapAdminServiceUpdateError(new Error('offline'))).toBe(
      'Could not reach the server. Check your connection and try again.',
    )
  })
})

describe('mapAdminServiceCreateError', () => {
  it('uses create-specific permission and failure copy', () => {
    expect(mapAdminServiceCreateError(new ApiError(403, 'Forbidden'))).toBe(
      'You do not have permission to create services.',
    )
    expect(mapAdminServiceCreateError(new ApiError(500, 'x'))).toBe(
      'Could not create the service. Try again later.',
    )
  })
})
