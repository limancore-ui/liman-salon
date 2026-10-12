import type {
  BlockType,
  BlockedPeriodCreateBody,
  BlockedPeriodItem,
  BlockedPeriodUpdateBody,
  WorkingHoursCreateBody,
  WorkingHoursItem,
  WorkingHoursUpdateBody,
} from '../types/schedule'

/** Backend wall-clock TIME (`HH:mm` or `HH:mm:ss`) → display `HH:mm`, no timezone conversion. */
export function formatTimeOfDay(timeStr: string): string {
  const [hours = '00', minutes = '00'] = timeStr.split(':')
  return `${hours.padStart(2, '0')}:${minutes.padStart(2, '0')}`
}

export function datetimeLocalToIso(value: string): string {
  return new Date(value).toISOString()
}

export function isoToDatetimeLocal(iso: string): string {
  const date = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export type BlockedPeriodFormState = {
  staffId: string
  startsAtLocal: string
  endsAtLocal: string
  reason: string
  blockType: BlockType
}

export const emptyBlockedForm = (): BlockedPeriodFormState => ({
  staffId: '',
  startsAtLocal: '',
  endsAtLocal: '',
  reason: '',
  blockType: 'manual',
})

export function blockedFormFromRow(row: BlockedPeriodItem): BlockedPeriodFormState {
  return {
    staffId: row.staff_id ?? '',
    startsAtLocal: isoToDatetimeLocal(row.starts_at),
    endsAtLocal: isoToDatetimeLocal(row.ends_at),
    reason: row.reason ?? '',
    blockType: (row.block_type as BlockType) || 'manual',
  }
}

export function formToCreateBody(form: BlockedPeriodFormState): BlockedPeriodCreateBody {
  return {
    staff_id: form.staffId === '' ? null : form.staffId,
    starts_at: datetimeLocalToIso(form.startsAtLocal),
    ends_at: datetimeLocalToIso(form.endsAtLocal),
    reason: form.reason.trim() === '' ? null : form.reason.trim(),
    block_type: form.blockType,
  }
}

export function formToUpdateBody(form: BlockedPeriodFormState): BlockedPeriodUpdateBody {
  return {
    staff_id: form.staffId === '' ? null : form.staffId,
    starts_at: datetimeLocalToIso(form.startsAtLocal),
    ends_at: datetimeLocalToIso(form.endsAtLocal),
    reason: form.reason.trim() === '' ? null : form.reason.trim(),
    block_type: form.blockType,
  }
}

/** Backend TIME → `<input type="time">` value (HH:mm), no timezone conversion. */
export function apiTimeToTimeInput(timeStr: string): string {
  const [hours = '00', minutes = '00'] = timeStr.split(':')
  return `${hours.padStart(2, '0')}:${minutes.padStart(2, '0')}`
}

/** `<input type="time">` value → API wall-clock time string. */
export function timeInputToApi(timeInput: string): string {
  if (timeInput.length === 5) {
    return `${timeInput}:00`
  }
  return timeInput
}

export type WorkingHoursFormState = {
  dayOfWeek: number
  startTime: string
  endTime: string
  effectiveFrom: string
  effectiveTo: string
}

export const emptyWorkingHoursForm = (): WorkingHoursFormState => ({
  dayOfWeek: 0,
  startTime: '',
  endTime: '',
  effectiveFrom: '',
  effectiveTo: '',
})

export function workingHoursFormFromRow(row: WorkingHoursItem): WorkingHoursFormState {
  return {
    dayOfWeek: row.day_of_week,
    startTime: apiTimeToTimeInput(row.start_time),
    endTime: apiTimeToTimeInput(row.end_time),
    effectiveFrom: row.effective_from ?? '',
    effectiveTo: row.effective_to ?? '',
  }
}

export function workingHoursFormToCreateBody(
  form: WorkingHoursFormState,
  staffId: string | null,
): WorkingHoursCreateBody {
  return {
    staff_id: staffId,
    day_of_week: form.dayOfWeek,
    start_time: timeInputToApi(form.startTime),
    end_time: timeInputToApi(form.endTime),
    effective_from: form.effectiveFrom === '' ? null : form.effectiveFrom,
    effective_to: form.effectiveTo === '' ? null : form.effectiveTo,
  }
}

export function workingHoursFormToUpdateBody(
  form: WorkingHoursFormState,
  staffId: string | null,
): WorkingHoursUpdateBody {
  return {
    staff_id: staffId,
    day_of_week: form.dayOfWeek,
    start_time: timeInputToApi(form.startTime),
    end_time: timeInputToApi(form.endTime),
    effective_from: form.effectiveFrom === '' ? null : form.effectiveFrom,
    effective_to: form.effectiveTo === '' ? null : form.effectiveTo,
  }
}
