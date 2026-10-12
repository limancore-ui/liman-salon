import { describe, expect, it } from 'vitest'
import {
  formatScheduleImpactReason,
  formatScheduleImpactReasons,
  isScheduleImpactReasonCode,
} from './mapScheduleImpactReason'

describe('isScheduleImpactReasonCode', () => {
  it('recognizes backend reason codes', () => {
    expect(isScheduleImpactReasonCode('outside_availability')).toBe(true)
    expect(isScheduleImpactReasonCode('staff_no_longer_performs_service')).toBe(true)
    expect(isScheduleImpactReasonCode('unknown')).toBe(false)
  })
})

describe('formatScheduleImpactReason', () => {
  it('returns Russian labels by default', () => {
    expect(formatScheduleImpactReason('outside_availability')).toContain('доступ')
    expect(formatScheduleImpactReason('staff_no_longer_performs_service')).toContain(
      'услугу',
    )
  })

  it('returns English labels when requested', () => {
    expect(formatScheduleImpactReason('outside_availability', 'en')).toContain(
      'available',
    )
    expect(formatScheduleImpactReason('staff_no_longer_performs_service', 'en')).toContain(
      'service',
    )
  })

  it('passes through unknown codes', () => {
    expect(formatScheduleImpactReason('custom_reason')).toBe('custom_reason')
  })
})

describe('formatScheduleImpactReasons', () => {
  it('deduplicates and maps multiple codes', () => {
    const labels = formatScheduleImpactReasons(
      ['outside_availability', 'outside_availability', 'staff_no_longer_performs_service'],
      'en',
    )
    expect(labels).toHaveLength(2)
    expect(labels[0]).toContain('available')
    expect(labels[1]).toContain('service')
  })
})
