import { ApiError } from './errors'
import type {
  SalonAppearance,
  SalonAppearancePatch,
} from '../types/salonAppearance'

type ApiErrorBody = {
  detail?: string
  code?: string
}

async function readApiError(response: Response): Promise<ApiError> {
  let detail = response.statusText
  let code: string | undefined
  try {
    const body = (await response.json()) as ApiErrorBody
    if (typeof body.detail === 'string') {
      detail = body.detail
    }
    if (typeof body.code === 'string') {
      code = body.code
    }
  } catch {
    /* ignore */
  }
  return new ApiError(response.status, detail, code)
}

export async function fetchSalonAppearance(
  token: string,
  salonId: string,
): Promise<SalonAppearance> {
  const response = await fetch(`/api/v1/salons/${salonId}/appearance`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as SalonAppearance
}

export async function patchSalonAppearance(
  token: string,
  salonId: string,
  body: SalonAppearancePatch,
): Promise<SalonAppearance> {
  const response = await fetch(`/api/v1/salons/${salonId}/appearance`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as SalonAppearance
}
