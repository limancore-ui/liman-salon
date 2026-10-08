import { describe, expect, it } from 'vitest'
import {
  bumpSmartGapRequestId,
  deriveSmartGapListPhase,
  filterSmartGapsForService,
  serviceStartFromSmartGap,
  shouldApplySmartGapResponse,
  smartGapListStatusMessage,
} from './createBookingSmartGaps'
import type { SmartGapOut } from '../types/smartGaps'

const serviceA = 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee'
const serviceB = 'ffffffff-ffff-4fff-8fff-ffffffffffff'

const gapFor = (serviceId: string): SmartGapOut => ({
  start: '2026-09-25T09:00:00Z',
  end: '2026-09-25T11:00:00Z',
  suitable_services: [
    {
      service_id: serviceId,
      name: 'Service',
      duration_minutes: 60,
      price_cents: 1000,
    },
  ],
})

describe('filterSmartGapsForService', () => {
  it('keeps gaps that list the selected service', () => {
    const gaps = [gapFor(serviceA), gapFor(serviceB)]
    expect(filterSmartGapsForService(gaps, serviceA)).toEqual([gapFor(serviceA)])
  })

  it('returns empty when no gap fits the service', () => {
    const gaps = [gapFor(serviceB)]
    expect(filterSmartGapsForService(gaps, serviceA)).toEqual([])
  })
})

describe('serviceStartFromSmartGap', () => {
  it('converts gap start UTC to salon-local datetime-local', () => {
    expect(serviceStartFromSmartGap('2026-09-25T13:30:00.000Z', 'America/New_York')).toBe(
      '2026-09-25T09:30',
    )
  })
})

describe('deriveSmartGapListPhase', () => {
  it('prefers loading over other states', () => {
    expect(
      deriveSmartGapListPhase({
        loading: true,
        error: 'err',
        searched: true,
        visibleGapCount: 3,
      }),
    ).toBe('loading')
  })

  it('reports empty after search with no visible gaps', () => {
    expect(
      deriveSmartGapListPhase({
        loading: false,
        error: null,
        searched: true,
        visibleGapCount: 0,
      }),
    ).toBe('empty')
  })

  it('reports ready when gaps are visible', () => {
    expect(
      deriveSmartGapListPhase({
        loading: false,
        error: null,
        searched: true,
        visibleGapCount: 2,
      }),
    ).toBe('ready')
  })
})

describe('smart gap request sequencing', () => {
  it('bumps request id for a new search or param reset', () => {
    expect(bumpSmartGapRequestId(0)).toBe(1)
    expect(bumpSmartGapRequestId(1)).toBe(2)
  })

  it('allows state updates only for the active request id', () => {
    expect(shouldApplySmartGapResponse(2, 2)).toBe(true)
    expect(shouldApplySmartGapResponse(1, 2)).toBe(false)
  })

  it('models stale response after newer search started', () => {
    let activeId = 0
    activeId = bumpSmartGapRequestId(activeId)
    const firstSearchId = activeId
    activeId = bumpSmartGapRequestId(activeId)
    const secondSearchId = activeId
    expect(shouldApplySmartGapResponse(firstSearchId, activeId)).toBe(false)
    expect(shouldApplySmartGapResponse(secondSearchId, activeId)).toBe(true)
  })

  it('models param change invalidating in-flight search and clearing loading', () => {
    let activeId = 0
    activeId = bumpSmartGapRequestId(activeId)
    const inFlightId = activeId
    activeId = bumpSmartGapRequestId(activeId)
    const shouldApplyStaleResults = shouldApplySmartGapResponse(inFlightId, activeId)
    const shouldClearLoadingForStale = shouldApplySmartGapResponse(inFlightId, activeId)
    expect(shouldApplyStaleResults).toBe(false)
    expect(shouldClearLoadingForStale).toBe(false)
  })
})

describe('smartGapListStatusMessage', () => {
  it('returns loading and empty copy', () => {
    expect(smartGapListStatusMessage('loading', null)).toBe('Loading free gaps…')
    expect(smartGapListStatusMessage('empty', null)).toContain('No free gaps')
  })

  it('returns API error message in error phase', () => {
    expect(smartGapListStatusMessage('error', 'Server busy')).toBe('Server busy')
  })
})
