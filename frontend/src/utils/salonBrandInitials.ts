/** Initials for salon brand mark when logo is missing or fails to load. */
export function salonBrandInitials(name: string): string {
  const parts = name
    .trim()
    .split(/\s+/)
    .filter((part) => part.length > 0)
  if (parts.length === 0) {
    return '?'
  }
  if (parts.length === 1) {
    return parts[0].slice(0, 2).toLocaleUpperCase('ru-RU')
  }
  const first = parts[0][0] ?? ''
  const second = parts[1][0] ?? ''
  return `${first}${second}`.toLocaleUpperCase('ru-RU')
}
