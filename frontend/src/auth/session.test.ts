import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { MeResponse, MySalonsResponse, SalonContextResponse } from '../types/auth'
import { loadAdminSession, switchAdminSalon } from './session'

const user: MeResponse = {
  user_id: 'user-1',
  email: 'owner@example.com',
  full_name: 'Owner',
}

const salonContext: SalonContextResponse = {
  user_id: 'user-1',
  salon_id: 'salon-a',
  role: 'owner',
  email: 'owner@example.com',
  salon_name: 'Alpha',
  salon_slug: 'alpha',
}

vi.mock('../api/auth', () => ({
  fetchCurrentUser: vi.fn(),
  fetchMySalons: vi.fn(),
  fetchSalonContext: vi.fn(),
}))

vi.mock('./storage', () => ({
  getSalonIdHintForContext: vi.fn(),
  setStoredAccessToken: vi.fn(),
  setStoredSalonIdHint: vi.fn(),
}))

import {
  fetchCurrentUser,
  fetchMySalons,
  fetchSalonContext,
} from '../api/auth'
import { getSalonIdHintForContext, setStoredSalonIdHint } from './storage'
import { ApiError } from '../api/errors'

function salonsResponse(
  items: MySalonsResponse['items'],
): MySalonsResponse {
  return { items }
}

beforeEach(() => {
  vi.mocked(fetchCurrentUser).mockReset()
  vi.mocked(fetchMySalons).mockReset()
  vi.mocked(fetchSalonContext).mockReset()
  vi.mocked(getSalonIdHintForContext).mockReset()
  vi.mocked(setStoredSalonIdHint).mockReset()
  vi.mocked(fetchCurrentUser).mockResolvedValue(user)
})

describe('loadAdminSession', () => {
  it('returns no_access when memberships are empty', async () => {
    vi.mocked(fetchMySalons).mockResolvedValue(salonsResponse([]))
    vi.mocked(getSalonIdHintForContext).mockReturnValue(null)

    const result = await loadAdminSession('token')
    expect(result.kind).toBe('no_access')
    expect(fetchSalonContext).not.toHaveBeenCalled()
  })

  it('auto-selects a single salon', async () => {
    vi.mocked(fetchMySalons).mockResolvedValue(
      salonsResponse([
        {
          salon_id: 'salon-a',
          salon_name: 'Alpha',
          salon_slug: 'alpha',
          role: 'owner',
        },
      ]),
    )
    vi.mocked(getSalonIdHintForContext).mockReturnValue(null)
    vi.mocked(fetchSalonContext).mockResolvedValue(salonContext)

    const result = await loadAdminSession('token')
    expect(result.kind).toBe('session')
    if (result.kind === 'session') {
      expect(result.session.salon.salon_id).toBe('salon-a')
      expect(result.session.salons).toHaveLength(1)
    }
    expect(setStoredSalonIdHint).toHaveBeenCalledWith('salon-a')
  })

  it('requires picker for multiple salons without a valid hint', async () => {
    vi.mocked(fetchMySalons).mockResolvedValue(
      salonsResponse([
        {
          salon_id: 'salon-a',
          salon_name: 'Alpha',
          salon_slug: 'alpha',
          role: 'owner',
        },
        {
          salon_id: 'salon-b',
          salon_name: 'Beta',
          salon_slug: 'beta',
          role: 'staff',
        },
      ]),
    )
    vi.mocked(getSalonIdHintForContext).mockReturnValue(null)

    const result = await loadAdminSession('token')
    expect(result.kind).toBe('picker')
  })

  it('recovers to picker when stored hint is stale', async () => {
    vi.mocked(fetchMySalons).mockResolvedValue(
      salonsResponse([
        {
          salon_id: 'salon-a',
          salon_name: 'Alpha',
          salon_slug: 'alpha',
          role: 'owner',
        },
        {
          salon_id: 'salon-b',
          salon_name: 'Beta',
          salon_slug: 'beta',
          role: 'staff',
        },
      ]),
    )
    vi.mocked(getSalonIdHintForContext).mockReturnValue('salon-a')
    vi.mocked(fetchSalonContext).mockRejectedValue(
      new ApiError(403, 'denied', 'salon_access_denied'),
    )

    const result = await loadAdminSession('token')
    expect(result.kind).toBe('picker')
  })
})

describe('switchAdminSalon', () => {
  it('updates session salon and hint', async () => {
    const nextContext: SalonContextResponse = {
      ...salonContext,
      salon_id: 'salon-b',
      salon_name: 'Beta',
      salon_slug: 'beta',
      role: 'staff',
    }
    vi.mocked(fetchSalonContext).mockResolvedValue(nextContext)

    const current = {
      token: 'token',
      user,
      salon: salonContext,
      salons: [
        {
          salon_id: 'salon-a',
          salon_name: 'Alpha',
          salon_slug: 'alpha',
          role: 'owner',
        },
        {
          salon_id: 'salon-b',
          salon_name: 'Beta',
          salon_slug: 'beta',
          role: 'staff',
        },
      ],
    }

    const next = await switchAdminSalon(current, 'salon-b')
    expect(next.salon.salon_id).toBe('salon-b')
    expect(setStoredSalonIdHint).toHaveBeenCalledWith('salon-b')
  })
})
