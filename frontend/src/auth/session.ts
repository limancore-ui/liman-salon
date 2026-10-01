import {
  fetchCurrentUser,
  fetchMySalons,
  fetchSalonContext,
} from '../api/auth'
import { ApiError } from '../api/errors'
import type {
  AdminSession,
  MeResponse,
  PendingWorkspaceAuth,
  SalonMembershipList,
} from '../types/auth'
import {
  getSalonIdHintForContext,
  setStoredAccessToken,
  setStoredSalonIdHint,
} from './storage'
import { resolveSalonSelection } from './workspace'

export class SalonContextResolutionError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'SalonContextResolutionError'
  }
}

export class NoSalonAccessError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'NoSalonAccessError'
  }
}

export type LoadAdminSessionResult =
  | { kind: 'session'; session: AdminSession }
  | { kind: 'no_access'; pending: PendingWorkspaceAuth }
  | { kind: 'picker'; pending: PendingWorkspaceAuth }

async function fetchSalonContextForMembership(
  token: string,
  salonId: string,
): Promise<AdminSession['salon']> {
  try {
    return await fetchSalonContext(token, salonId)
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
}

async function buildSession(
  token: string,
  user: MeResponse,
  salons: SalonMembershipList,
  salonId: string,
): Promise<AdminSession> {
  const salon = await fetchSalonContextForMembership(token, salonId)
  setStoredSalonIdHint(salon.salon_id)
  return { token, user, salon, salons }
}

export async function loadAdminSession(
  token: string,
): Promise<LoadAdminSessionResult> {
  const user = await fetchCurrentUser(token)
  const { items: salons } = await fetchMySalons(token)
  const selection = resolveSalonSelection(salons, getSalonIdHintForContext())

  if (selection.kind === 'none') {
    return {
      kind: 'no_access',
      pending: { token, user, salons },
    }
  }

  if (selection.kind === 'picker') {
    return {
      kind: 'picker',
      pending: { token, user, salons },
    }
  }

  try {
    const session = await buildSession(token, user, salons, selection.salonId)
    return { kind: 'session', session }
  } catch {
    if (salons.length > 1) {
      return {
        kind: 'picker',
        pending: { token, user, salons },
      }
    }
    return {
      kind: 'no_access',
      pending: { token, user, salons },
    }
  }
}

export async function completeWorkspaceSelection(
  pending: PendingWorkspaceAuth,
  salonId: string,
): Promise<AdminSession> {
  const session = await buildSession(
    pending.token,
    pending.user,
    pending.salons,
    salonId,
  )
  return session
}

export async function switchAdminSalon(
  session: AdminSession,
  salonId: string,
): Promise<AdminSession> {
  if (session.salon.salon_id === salonId) {
    return session
  }
  const salon = await fetchSalonContextForMembership(session.token, salonId)
  setStoredSalonIdHint(salon.salon_id)
  return { ...session, salon }
}

export async function establishAdminSession(
  token: string,
): Promise<LoadAdminSessionResult> {
  setStoredAccessToken(token)
  return loadAdminSession(token)
}
