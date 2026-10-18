import { ApiError } from '../api/errors'
import type { StaffCreateBody, StaffListItem, StaffUpdateBody } from '../types/staff'
import { t } from '../i18n'
import { adminUserErrorMessage } from './adminUserError'

const COLOR_HEX = /^#[0-9A-Fa-f]{6}$/
const TITLE_MAX_LENGTH = 100

export function staffUnsupportedClearMessage(): string {
  return t('admin.staff.unsupportedClear')
}

/** @deprecated use staffUnsupportedClearMessage() */
export const STAFF_UNSUPPORTED_CLEAR_MESSAGE = staffUnsupportedClearMessage()

export type StaffFormState = {
  displayName: string
  title: string
  bio: string
  colorHex: string
  isBookable: boolean
  isActive: boolean
  sortOrder: string
}

export type ParsedStaffFormValues = {
  display_name: string
  title: string | null
  bio: string | null
  color_hex: string | null
  is_bookable: boolean
  is_active: boolean
  sort_order: number
}

export function emptyStaffForm(): StaffFormState {
  return {
    displayName: '',
    title: '',
    bio: '',
    colorHex: '',
    isBookable: true,
    isActive: true,
    sortOrder: '0',
  }
}

export function staffFormFromRow(row: StaffListItem): StaffFormState {
  return {
    displayName: row.display_name,
    title: row.title ?? '',
    bio: row.bio ?? '',
    colorHex: row.color_hex ?? '',
    isBookable: row.is_bookable,
    isActive: row.is_active,
    sortOrder: String(row.sort_order),
  }
}

function parseNonNegativeInt(raw: string): number | null {
  const trimmed = raw.trim()
  if (trimmed === '') {
    return 0
  }
  const parsed = Number(trimmed)
  if (!Number.isInteger(parsed) || parsed < 0) {
    return null
  }
  return parsed
}

export function parseStaffFormFields(form: StaffFormState): ParsedStaffFormValues | string {
  const display_name = form.displayName.trim()
  if (display_name === '') {
    return t('admin.staff.displayNameRequired')
  }

  const sort_order = parseNonNegativeInt(form.sortOrder)
  if (sort_order === null) {
    return t('admin.staff.sortInvalid')
  }

  const colorTrimmed = form.colorHex.trim()
  if (colorTrimmed !== '' && !COLOR_HEX.test(colorTrimmed)) {
    return t('admin.staff.colorInvalid')
  }

  const titleTrimmed = form.title.trim()
  if (titleTrimmed.length > TITLE_MAX_LENGTH) {
    return t('admin.staff.titleTooLong', { max: TITLE_MAX_LENGTH })
  }
  const bioTrimmed = form.bio.trim()

  return {
    display_name,
    title: titleTrimmed === '' ? null : titleTrimmed,
    bio: bioTrimmed === '' ? null : bioTrimmed,
    color_hex: colorTrimmed === '' ? null : colorTrimmed,
    is_bookable: form.isBookable,
    is_active: form.isActive,
    sort_order,
  }
}

export function buildStaffCreateBody(parsed: ParsedStaffFormValues): StaffCreateBody {
  const body: StaffCreateBody = { display_name: parsed.display_name }

  if (parsed.title !== null) {
    body.title = parsed.title
  }
  if (parsed.bio !== null) {
    body.bio = parsed.bio
  }
  if (parsed.color_hex !== null) {
    body.color_hex = parsed.color_hex
  }
  if (!parsed.is_bookable) {
    body.is_bookable = false
  }
  if (!parsed.is_active) {
    body.is_active = false
  }
  if (parsed.sort_order !== 0) {
    body.sort_order = parsed.sort_order
  }

  return body
}

function isUnsupportedClear(
  parsedValue: string | null,
  originalValue: string | null,
): boolean {
  return parsedValue === null && originalValue !== null
}

/** True when the user cleared a field the API cannot unset (PATCH null is ignored server-side). */
export function hasStaffUnsupportedClear(
  original: StaffListItem,
  parsed: ParsedStaffFormValues,
): boolean {
  return (
    isUnsupportedClear(parsed.title, original.title) ||
    isUnsupportedClear(parsed.bio, original.bio) ||
    isUnsupportedClear(parsed.color_hex, original.color_hex)
  )
}

/** PATCH body containing only fields that differ from the listed staff row. */
export function buildStaffUpdatePatch(
  original: StaffListItem,
  parsed: ParsedStaffFormValues,
): StaffUpdateBody {
  const body: StaffUpdateBody = {}

  if (parsed.display_name !== original.display_name) {
    body.display_name = parsed.display_name
  }
  if (parsed.title !== original.title && !isUnsupportedClear(parsed.title, original.title)) {
    body.title = parsed.title ?? undefined
  }
  if (parsed.bio !== original.bio && !isUnsupportedClear(parsed.bio, original.bio)) {
    body.bio = parsed.bio ?? undefined
  }
  if (
    parsed.color_hex !== original.color_hex &&
    !isUnsupportedClear(parsed.color_hex, original.color_hex)
  ) {
    body.color_hex = parsed.color_hex ?? undefined
  }
  if (parsed.is_bookable !== original.is_bookable) {
    body.is_bookable = parsed.is_bookable
  }
  if (parsed.is_active !== original.is_active) {
    body.is_active = parsed.is_active
  }
  if (parsed.sort_order !== original.sort_order) {
    body.sort_order = parsed.sort_order
  }

  return body
}

function mapAdminStaffNetworkError(err: unknown, action: 'create' | 'update'): string {
  if (err instanceof ApiError && err.status === 403) {
    return action === 'create'
      ? t('admin.staff.noPermissionCreate')
      : t('admin.staff.noPermissionUpdate')
  }
  return adminUserErrorMessage(
    err,
    action === 'create' ? 'admin.staff.createFailed' : 'admin.staff.updateFailed',
  )
}

export function mapAdminStaffCreateError(err: unknown): string {
  return mapAdminStaffNetworkError(err, 'create')
}

export function mapAdminStaffUpdateError(err: unknown): string {
  return mapAdminStaffNetworkError(err, 'update')
}

export function staffActiveToggleLabel(isActive: boolean): string {
  return isActive ? t('admin.staff.deactivate') : t('admin.staff.activate')
}

export function staffBookableToggleLabel(isBookable: boolean): string {
  return isBookable ? t('admin.staff.makeUnbookable') : t('admin.staff.makeBookable')
}

export function staffActiveTogglePatch(isActive: boolean): Pick<StaffUpdateBody, 'is_active'> {
  return { is_active: !isActive }
}

export function staffBookableTogglePatch(
  isBookable: boolean,
): Pick<StaffUpdateBody, 'is_bookable'> {
  return { is_bookable: !isBookable }
}
