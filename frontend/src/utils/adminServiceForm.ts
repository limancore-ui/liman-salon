import { ApiError } from '../api/errors'
import type { ServiceListItem, ServiceUpdateBody } from '../types/services'
import { t } from '../i18n'
import { adminUserErrorMessage } from './adminUserError'

export type ServiceFormState = {
  name: string
  description: string
  durationMinutes: string
  priceMajor: string
  bufferBefore: string
  bufferAfter: string
  sortOrder: string
}

export type ParsedServiceFormValues = {
  name: string
  description: string | null
  duration_minutes: number
  price_cents: number
  buffer_before_minutes: number
  buffer_after_minutes: number
  sort_order: number
}

export function serviceFormFromRow(row: ServiceListItem): ServiceFormState {
  return {
    name: row.name,
    description: row.description ?? '',
    durationMinutes: String(row.duration_minutes),
    priceMajor: String(row.price_cents / 100),
    bufferBefore: String(row.buffer_before_minutes),
    bufferAfter: String(row.buffer_after_minutes),
    sortOrder: String(row.sort_order),
  }
}

/** PATCH body containing only fields that differ from the listed service row. */
export function buildServiceUpdatePatch(
  original: ServiceListItem,
  parsed: ParsedServiceFormValues,
): ServiceUpdateBody {
  const body: ServiceUpdateBody = {}

  if (parsed.name !== original.name) {
    body.name = parsed.name
  }
  if (parsed.description !== original.description) {
    body.description = parsed.description
  }
  if (parsed.duration_minutes !== original.duration_minutes) {
    body.duration_minutes = parsed.duration_minutes
  }
  if (parsed.price_cents !== original.price_cents) {
    body.price_cents = parsed.price_cents
  }
  if (parsed.buffer_before_minutes !== original.buffer_before_minutes) {
    body.buffer_before_minutes = parsed.buffer_before_minutes
  }
  if (parsed.buffer_after_minutes !== original.buffer_after_minutes) {
    body.buffer_after_minutes = parsed.buffer_after_minutes
  }
  if (parsed.sort_order !== original.sort_order) {
    body.sort_order = parsed.sort_order
  }

  return body
}

function mapAdminServiceNetworkError(err: unknown): string {
  if (err instanceof ApiError && err.status === 403) {
    return t('admin.services.noPermissionUpdate')
  }
  return adminUserErrorMessage(err, 'admin.services.updateFailed')
}

export function mapAdminServiceCreateError(err: unknown): string {
  if (err instanceof ApiError && err.status === 403) {
    return t('admin.services.noPermissionCreate')
  }
  return adminUserErrorMessage(err, 'admin.services.createFailed')
}

/** Edit form saves and active/inactive toggles. */
export function mapAdminServiceUpdateError(err: unknown): string {
  return mapAdminServiceNetworkError(err)
}

export function serviceActiveToggleLabel(isActive: boolean): string {
  return isActive ? t('admin.services.deactivate') : t('admin.services.activate')
}

export function serviceActiveTogglePatch(isActive: boolean): Pick<ServiceUpdateBody, 'is_active'> {
  return { is_active: !isActive }
}
