import { describe, expect, it } from 'vitest'
import {
  buildBlockedPeriodCreateImpactChange,
  buildBlockedPeriodCreateImpactChangeFromForm,
  buildBlockedPeriodDeleteImpactChange,
  buildBlockedPeriodUpdateImpactChange,
  buildBlockedPeriodUpdateImpactChangeFromForm,
  buildStaffServiceDetachImpactChange,
  buildWorkingHoursCreateImpactChange,
  buildWorkingHoursCreateImpactChangeFromForm,
  buildWorkingHoursDeleteImpactChange,
  buildWorkingHoursUpdateImpactChange,
  buildWorkingHoursUpdateImpactChangeFromForm,
} from './scheduleImpactChange'
import type { BlockedPeriodFormState, WorkingHoursFormState } from './scheduleFormBodies'

const WH_FORM: WorkingHoursFormState = {
  dayOfWeek: 2,
  startTime: '09:00',
  endTime: '17:00',
  effectiveFrom: '',
  effectiveTo: '2026-12-31',
}

const BP_FORM: BlockedPeriodFormState = {
  staffId: 'staff-uuid',
  startsAtLocal: '2026-08-01T09:00',
  endsAtLocal: '2026-08-01T12:00',
  reason: '  Meeting  ',
  blockType: 'manual',
}

describe('working hours impact change builders', () => {
  it('buildWorkingHoursCreateImpactChange sets kind and staff scope', () => {
    expect(
      buildWorkingHoursCreateImpactChange({
        staff_id: null,
        day_of_week: 1,
        start_time: '09:00:00',
        end_time: '17:00:00',
      }),
    ).toEqual({
      kind: 'working_hours.create',
      staff_id: null,
      day_of_week: 1,
      start_time: '09:00:00',
      end_time: '17:00:00',
    })
  })

  it('buildWorkingHoursCreateImpactChangeFromForm uses form mapper', () => {
    const change = buildWorkingHoursCreateImpactChangeFromForm(WH_FORM, 'staff-1')
    expect(change.kind).toBe('working_hours.create')
    expect(change.staff_id).toBe('staff-1')
    expect(change.day_of_week).toBe(2)
    expect(change.start_time).toBe('09:00:00')
    expect(change.end_time).toBe('17:00:00')
    expect(change.effective_to).toBe('2026-12-31')
  })

  it('buildWorkingHoursUpdateImpactChange includes working_hours_id', () => {
    expect(
      buildWorkingHoursUpdateImpactChange('wh-id', {
        end_time: '15:00:00',
      }),
    ).toEqual({
      kind: 'working_hours.update',
      working_hours_id: 'wh-id',
      end_time: '15:00:00',
    })
  })

  it('buildWorkingHoursUpdateImpactChangeFromForm merges id and form body', () => {
    const change = buildWorkingHoursUpdateImpactChangeFromForm(
      'wh-99',
      WH_FORM,
      null,
    )
    expect(change.working_hours_id).toBe('wh-99')
    expect(change.kind).toBe('working_hours.update')
    expect(change.staff_id).toBeNull()
    expect(change.start_time).toBe('09:00:00')
  })

  it('buildWorkingHoursDeleteImpactChange', () => {
    expect(buildWorkingHoursDeleteImpactChange('wh-del')).toEqual({
      kind: 'working_hours.delete',
      working_hours_id: 'wh-del',
    })
  })
})

describe('blocked period impact change builders', () => {
  it('buildBlockedPeriodCreateImpactChange', () => {
    expect(
      buildBlockedPeriodCreateImpactChange({
        staff_id: null,
        starts_at: '2026-08-01T09:00:00+00:00',
        ends_at: '2026-08-01T12:00:00+00:00',
        block_type: 'holiday',
      }),
    ).toMatchObject({
      kind: 'blocked_period.create',
      staff_id: null,
      block_type: 'holiday',
    })
  })

  it('buildBlockedPeriodCreateImpactChangeFromForm maps staff and reason trim', () => {
    const change = buildBlockedPeriodCreateImpactChangeFromForm(BP_FORM)
    expect(change.kind).toBe('blocked_period.create')
    expect(change.staff_id).toBe('staff-uuid')
    expect(change.reason).toBe('Meeting')
    expect(change.starts_at).toMatch(/2026-08-01T/)
  })

  it('buildBlockedPeriodUpdateImpactChange includes blocked_period_id', () => {
    expect(
      buildBlockedPeriodUpdateImpactChange('bp-1', { reason: 'Updated' }),
    ).toEqual({
      kind: 'blocked_period.update',
      blocked_period_id: 'bp-1',
      reason: 'Updated',
    })
  })

  it('buildBlockedPeriodUpdateImpactChangeFromForm', () => {
    const change = buildBlockedPeriodUpdateImpactChangeFromForm('bp-42', BP_FORM)
    expect(change.blocked_period_id).toBe('bp-42')
    expect(change.kind).toBe('blocked_period.update')
    expect(change.block_type).toBe('manual')
  })

  it('buildBlockedPeriodDeleteImpactChange', () => {
    expect(buildBlockedPeriodDeleteImpactChange('bp-del')).toEqual({
      kind: 'blocked_period.delete',
      blocked_period_id: 'bp-del',
    })
  })
})

describe('staff service detach impact change builder', () => {
  it('buildStaffServiceDetachImpactChange', () => {
    expect(
      buildStaffServiceDetachImpactChange('staff-a', 'svc-b'),
    ).toEqual({
      kind: 'staff_service.detach',
      staff_id: 'staff-a',
      service_id: 'svc-b',
    })
  })
})
