import { ApiError } from '../api/errors'
import type { StaffCreateBody, StaffListItem, StaffUpdateBody } from '../types/staff'

const COLOR_HEX = /^#[0-9A-Fa-f]{6}$/
const TITLE_MAX_LENGTH = 100

export const STAFF_UNSUPPORTED_CLEAR_MESSAGE =
  'Clearing title, bio, or color is not supported. Leave the field unchanged or enter a new value.'

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
    return 'Display name is required.'
  }

  const sort_order = parseNonNegativeInt(form.sortOrder)
  if (sort_order === null) {
    return 'Sort order must be a non-negative whole number.'
  }

  const colorTrimmed = form.colorHex.trim()
  if (colorTrimmed !== '' && !COLOR_HEX.test(colorTrimmed)) {
    return 'Color must be a hex value like #AABBCC.'
  }

  const titleTrimmed = form.title.trim()
  if (titleTrimmed.length > TITLE_MAX_LENGTH) {
    return `Title must be at most ${TITLE_MAX_LENGTH} characters.`
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
  if (err instanceof ApiError) {
    if (err.status === 403) {
      return action === 'create'
        ? 'You do not have permission to create staff.'
        : 'You do not have permission to update staff.'
    }
    if (err.status === 422 && err.message.trim() !== '') {
      return err.message
    }
    if (err.status === 0) {
      return 'Could not reach the server. Check your connection and try again.'
    }
    return action === 'create'
      ? 'Could not create staff. Try again later.'
      : 'Could not update staff. Try again later.'
  }
  return 'Could not reach the server. Check your connection and try again.'
}

export function mapAdminStaffCreateError(err: unknown): string {
  return mapAdminStaffNetworkError(err, 'create')
}

export function mapAdminStaffUpdateError(err: unknown): string {
  return mapAdminStaffNetworkError(err, 'update')
}

export function staffActiveToggleLabel(isActive: boolean): 'Activate' | 'Deactivate' {
  return isActive ? 'Deactivate' : 'Activate'
}

export function staffBookableToggleLabel(isBookable: boolean): 'Make unbookable' | 'Make bookable' {
  return isBookable ? 'Make unbookable' : 'Make bookable'
}

export function staffActiveTogglePatch(isActive: boolean): Pick<StaffUpdateBody, 'is_active'> {
  return { is_active: !isActive }
}

export function staffBookableTogglePatch(
  isBookable: boolean,
): Pick<StaffUpdateBody, 'is_bookable'> {
  return { is_bookable: !isBookable }
}
