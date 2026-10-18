const HEX_COLOR_RE = /^#[0-9A-Fa-f]{6}$/

export function isValidHexColor(value: string): boolean {
  return HEX_COLOR_RE.test(value.trim())
}

export function normalizeHexColor(value: string): string {
  return value.trim().toLowerCase()
}

/** Empty string clears the override; invalid non-empty values return null. */
export function parseOptionalHexColor(
  value: string,
): { ok: true; color: string | null } | { ok: false } {
  const trimmed = value.trim()
  if (!trimmed) {
    return { ok: true, color: null }
  }
  if (!isValidHexColor(trimmed)) {
    return { ok: false }
  }
  return { ok: true, color: normalizeHexColor(trimmed) }
}
