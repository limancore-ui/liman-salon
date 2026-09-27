const ACCESS_TOKEN_KEY = 'liman_admin_access_token'
const SALON_ID_KEY = 'liman_admin_salon_id'

export function getStoredAccessToken(): string | null {
  try {
    const value = localStorage.getItem(ACCESS_TOKEN_KEY)
    return value && value.trim() ? value : null
  } catch {
    return null
  }
}

export function setStoredAccessToken(token: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, token)
}

export function clearStoredAccessToken(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
}

/** Salon id hint for context resolution; only written after a successful context response. */
export function getStoredSalonIdHint(): string | null {
  try {
    const value = localStorage.getItem(SALON_ID_KEY)
    return value && value.trim() ? value : null
  } catch {
    return null
  }
}

export function setStoredSalonIdHint(salonId: string): void {
  localStorage.setItem(SALON_ID_KEY, salonId)
}

export function clearStoredSalonIdHint(): void {
  localStorage.removeItem(SALON_ID_KEY)
}

export function clearAdminAuthStorage(): void {
  clearStoredAccessToken()
  clearStoredSalonIdHint()
}

/** Optional build-time salon id for first admin sign-in until a memberships list API exists. */
export function getConfiguredSalonIdHint(): string | null {
  const fromEnv = import.meta.env.VITE_ADMIN_SALON_ID
  if (typeof fromEnv === 'string' && fromEnv.trim()) {
    return fromEnv.trim()
  }
  return null
}

export function getSalonIdHintForContext(): string | null {
  return getStoredSalonIdHint() ?? getConfiguredSalonIdHint()
}
