import { describe, expect, it } from 'vitest'
import {
  buildScheduleImpactDisplayResponse,
  isScheduleImpactConfirmDisabled,
  mergeImpactPages,
  paginationFromLoadMorePage,
} from './scheduleImpactPreviewState'
import type { ScheduleImpactBookingRow } from '../types/schedule'
import { makeScheduleImpactPreviewResponse } from '../components/scheduleImpactPreviewFixtures'

const row = (
  id: string,
  overrides: Partial<ScheduleImpactBookingRow> = {},
): ScheduleImpactBookingRow => ({
  booking_id: id,
  status: 'confirmed',
  is_in_progress: false,
  starts_at: '2026-01-01T10:00:00+00:00',
  ends_at: '2026-01-01T11:00:00+00:00',
  staff_id: 'staff-1',
  service_id: 'svc-1',
  customer_name: 'Customer',
  service_name: 'Cut',
  reasons: ['outside_availability'],
  ...overrides,
})

describe('mergeImpactPages', () => {
  it('appends new rows and skips duplicate booking ids', () => {
    const merged = mergeImpactPages([row('a')], [row('b'), row('a')])
    expect(merged.map((r) => r.booking_id)).toEqual(['a', 'b'])
  })
})

describe('buildScheduleImpactDisplayResponse', () => {
  it('keeps first-page metadata and swaps pagination only', () => {
    const first = makeScheduleImpactPreviewResponse({
      as_of: '2026-01-01T12:00:00+00:00',
      impact_fingerprint: 'a'.repeat(64),
      counts: { total_impacted: 5, by_reason: {} },
      pagination: {
        offset: 0,
        limit: 1,
        returned: 1,
        total_impacted: 5,
        has_more: true,
      },
    })
    const nextPagination = paginationFromLoadMorePage(
      makeScheduleImpactPreviewResponse({
        pagination: {
          offset: 1,
          limit: 1,
          returned: 1,
          total_impacted: 5,
          has_more: false,
        },
        impact_fingerprint: 'b'.repeat(64),
        as_of: '2026-01-02T12:00:00+00:00',
      }),
    )
    const display = buildScheduleImpactDisplayResponse(first, nextPagination)
    expect(display.pagination).toEqual(nextPagination)
    expect(display.impact_fingerprint).toBe(first.impact_fingerprint)
    expect(display.as_of).toBe(first.as_of)
    expect(display.counts).toEqual(first.counts)
  })
})

describe('isScheduleImpactConfirmDisabled', () => {
  it('disables while loading or on error', () => {
    expect(
      isScheduleImpactConfirmDisabled({
        loading: true,
        loadingMore: false,
        error: null,
        hasResponse: true,
        requiresAcknowledgement: false,
        acknowledgementChecked: false,
      }),
    ).toBe(true)
    expect(
      isScheduleImpactConfirmDisabled({
        loading: false,
        loadingMore: false,
        error: 'fail',
        hasResponse: false,
        requiresAcknowledgement: false,
        acknowledgementChecked: false,
      }),
    ).toBe(true)
  })

  it('disables while loading more', () => {
    expect(
      isScheduleImpactConfirmDisabled({
        loading: false,
        loadingMore: true,
        error: null,
        hasResponse: true,
        requiresAcknowledgement: false,
        acknowledgementChecked: true,
      }),
    ).toBe(true)
  })

  it('requires acknowledgement when policy says so', () => {
    expect(
      isScheduleImpactConfirmDisabled({
        loading: false,
        loadingMore: false,
        error: null,
        hasResponse: true,
        requiresAcknowledgement: true,
        acknowledgementChecked: false,
      }),
    ).toBe(true)
    expect(
      isScheduleImpactConfirmDisabled({
        loading: false,
        loadingMore: false,
        error: null,
        hasResponse: true,
        requiresAcknowledgement: true,
        acknowledgementChecked: true,
      }),
    ).toBe(false)
  })
})

