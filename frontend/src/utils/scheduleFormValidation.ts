import type { WorkingHoursFormState } from './scheduleFormBodies'
import { t } from '../i18n'

export function workingHoursTimesRequiredMessage(): string {
  return t('admin.schedule.timesRequired')
}
export function workingHoursTimeOrderMessage(): string {
  return t('admin.schedule.timeOrder')
}

/** @deprecated use workingHoursTimesRequiredMessage() */
export const WORKING_HOURS_TIMES_REQUIRED_MESSAGE = workingHoursTimesRequiredMessage()
/** @deprecated use workingHoursTimeOrderMessage() */
export const WORKING_HOURS_TIME_ORDER_MESSAGE = workingHoursTimeOrderMessage()

const TIME_PATTERN = /^(\d{1,2}):(\d{2})(?::(\d{2}))?$/

/** `HH:mm` or `HH:mm:ss` → seconds since midnight, or null when malformed. */
function timeToSeconds(value: string): number | null {
  const match = TIME_PATTERN.exec(value.trim())
  if (match === null) {
    return null
  }
  const hours = Number(match[1])
  const minutes = Number(match[2])
  const seconds = match[3] === undefined ? 0 : Number(match[3])
  if (hours > 23 || minutes > 59 || seconds > 59) {
    return null
  }
  return hours * 3600 + minutes * 60 + seconds
}

/**
 * Client pre-check for a working-hours form before any preview or create request.
 * Returns a user-facing message, or null when the form is valid.
 */
export function validateWorkingHoursForm(
  form: Pick<WorkingHoursFormState, 'startTime' | 'endTime'>,
): string | null {
  if (form.startTime.trim() === '' || form.endTime.trim() === '') {
    return WORKING_HOURS_TIMES_REQUIRED_MESSAGE
  }
  const start = timeToSeconds(form.startTime)
  const end = timeToSeconds(form.endTime)
  if (start === null || end === null) {
    return WORKING_HOURS_TIMES_REQUIRED_MESSAGE
  }
  if (start >= end) {
    return WORKING_HOURS_TIME_ORDER_MESSAGE
  }
  return null
}
