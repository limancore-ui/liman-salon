import type { ScheduleImpactPreviewResponse } from '../types/schedule'

export function makeScheduleImpactPreviewResponse(
  overrides: Partial<ScheduleImpactPreviewResponse> = {},
): ScheduleImpactPreviewResponse {
  return {
    as_of: '2026-01-01T12:00:00+00:00',
    change_summary: {
      kind: 'working_hours.delete',
      affected_staff_ids: ['staff-1'],
      horizon: {
        starts_at_from: '2026-01-01T12:00:00+00:00',
        starts_at_to: '2026-04-01T12:00:00+00:00',
        days: 90,
      },
    },
    impacts: [],
    counts: { total_impacted: 0, by_reason: {} },
    pagination: {
      offset: 0,
      limit: 50,
      returned: 0,
      total_impacted: 0,
      has_more: false,
    },
    commit_policy: {
      allow_commit_with_impacts: true,
      requires_acknowledgement: false,
    },
    impact_fingerprint: 'f'.repeat(64),
    ...overrides,
  }
}
