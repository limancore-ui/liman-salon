import { fetchCurrentUser, fetchSalonContext } from '../api/auth'
import { ApiError } from '../api/errors'
import type { AdminSession } from '../types/auth'
import {
  getSalonIdHintForContext,
  setStoredAccessToken,
  setStoredSalonIdHint,
} from './storage'

export class SalonContextResolutionError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'SalonContextResolutionError'
  }
}

export async function loadAdminSession(token: string): Promise<AdminSession> {
  const user = await fetchCurrentUser(token)
  const salonIdHint = getSalonIdHintForContext()
  if (!salonIdHint) {
    throw new SalonContextResolutionError(
      'No salon workspace is configured for this sign-in.',
    )
  }

  let salon
  try {
    salon = await fetchSalonContext(token, salonIdHint)
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) {
      throw new SalonContextResolutionError(
        'You do not have access to this salon workspace.',
      )
    }
    if (error instanceof ApiError && error.status === 404) {
      throw new SalonContextResolutionError('Salon workspace was not found.')
    }
    throw error
  }

  setStoredSalonIdHint(salon.salon_id)
  return { token, user, salon }
}

export async function establishAdminSession(
  token: string,
): Promise<AdminSession> {
  setStoredAccessToken(token)
  return loadAdminSession(token)
}
