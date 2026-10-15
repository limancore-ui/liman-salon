import type {
  BlockedPeriodCreateBody,
  BlockedPeriodUpdateBody,
  BlockedPeriodCreateImpactChange,
  BlockedPeriodDeleteImpactChange,
  BlockedPeriodUpdateImpactChange,
  StaffServiceDetachImpactChange,
  WorkingHoursCreateProposal,
  WorkingHoursCreateImpactChange,
  WorkingHoursDeleteImpactChange,
  WorkingHoursUpdateBody,
  WorkingHoursUpdateImpactChange,
} from '../types/schedule'
import type { BlockedPeriodFormState, WorkingHoursFormState } from './scheduleFormBodies'
import {
  formToCreateBody,
  formToUpdateBody,
  workingHoursFormToCreateBody,
  workingHoursFormToUpdateBody,
} from './scheduleFormBodies'

export function buildWorkingHoursCreateImpactChange(
  body: WorkingHoursCreateProposal,
): WorkingHoursCreateImpactChange {
  return { kind: 'working_hours.create', ...body }
}

export function buildWorkingHoursCreateImpactChangeFromForm(
  form: WorkingHoursFormState,
  staffId: string | null,
): WorkingHoursCreateImpactChange {
  return buildWorkingHoursCreateImpactChange(
    workingHoursFormToCreateBody(form, staffId),
  )
}

export function buildWorkingHoursUpdateImpactChange(
  workingHoursId: string,
  body: WorkingHoursUpdateBody,
): WorkingHoursUpdateImpactChange {
  return { kind: 'working_hours.update', working_hours_id: workingHoursId, ...body }
}

export function buildWorkingHoursUpdateImpactChangeFromForm(
  workingHoursId: string,
  form: WorkingHoursFormState,
  staffId: string | null,
): WorkingHoursUpdateImpactChange {
  return buildWorkingHoursUpdateImpactChange(
    workingHoursId,
    workingHoursFormToUpdateBody(form, staffId),
  )
}

export function buildWorkingHoursDeleteImpactChange(
  workingHoursId: string,
): WorkingHoursDeleteImpactChange {
  return { kind: 'working_hours.delete', working_hours_id: workingHoursId }
}

export function buildBlockedPeriodCreateImpactChange(
  body: BlockedPeriodCreateBody,
): BlockedPeriodCreateImpactChange {
  return { kind: 'blocked_period.create', ...body }
}

export function buildBlockedPeriodCreateImpactChangeFromForm(
  form: BlockedPeriodFormState,
): BlockedPeriodCreateImpactChange {
  return buildBlockedPeriodCreateImpactChange(formToCreateBody(form))
}

export function buildBlockedPeriodUpdateImpactChange(
  blockedPeriodId: string,
  body: BlockedPeriodUpdateBody,
): BlockedPeriodUpdateImpactChange {
  return {
    kind: 'blocked_period.update',
    blocked_period_id: blockedPeriodId,
    ...body,
  }
}

export function buildBlockedPeriodUpdateImpactChangeFromForm(
  blockedPeriodId: string,
  form: BlockedPeriodFormState,
): BlockedPeriodUpdateImpactChange {
  return buildBlockedPeriodUpdateImpactChange(
    blockedPeriodId,
    formToUpdateBody(form),
  )
}

export function buildBlockedPeriodDeleteImpactChange(
  blockedPeriodId: string,
): BlockedPeriodDeleteImpactChange {
  return { kind: 'blocked_period.delete', blocked_period_id: blockedPeriodId }
}

export function buildStaffServiceDetachImpactChange(
  staffId: string,
  serviceId: string,
): StaffServiceDetachImpactChange {
  return {
    kind: 'staff_service.detach',
    staff_id: staffId,
    service_id: serviceId,
  }
}
