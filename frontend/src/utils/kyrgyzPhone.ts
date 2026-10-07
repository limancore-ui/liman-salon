/**
 * Kyrgyz phone UX helpers.
 *
 * The public form shows a fixed `+996` prefix and the user types only the 9
 * local digits. Form state holds those digits; the API receives the canonical
 * `+996XXXXXXXXX` value. The backend remains the source of truth for validation.
 */

export const KG_PHONE_PREFIX = '+996'
export const KG_PHONE_LOCAL_LENGTH = 9

/** Keep ASCII digits only, drop a pasted `+996`/`996` prefix, cap at 9 digits. */
export function sanitizeKgLocalPhone(input: string): string {
  let digits = input.replace(/\D/g, '')
  if (digits.startsWith('996') && digits.length > KG_PHONE_LOCAL_LENGTH) {
    digits = digits.slice(3)
  }
  return digits.slice(0, KG_PHONE_LOCAL_LENGTH)
}

export function isCompleteKgLocalPhone(local: string): boolean {
  return /^[0-9]{9}$/.test(local)
}

/** Canonical API value from the 9 local digits (`+996` + digits). */
export function toCanonicalKgPhone(local: string): string {
  return `${KG_PHONE_PREFIX}${local}`
}
