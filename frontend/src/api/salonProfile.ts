import { ApiError } from './errors'
import type { SalonProfile, SalonProfilePatch } from '../types/salonProfile'

type ApiErrorBody = {
  detail?: string | Array<{ msg?: string }>
  code?: string
}

async function readApiError(response: Response): Promise<ApiError> {
  let detail = response.statusText
  let code: string | undefined
  try {
    const body = (await response.json()) as ApiErrorBody
    if (typeof body.detail === 'string') {
      detail = body.detail
    } else if (Array.isArray(body.detail) && body.detail[0]?.msg) {
      detail = String(body.detail[0].msg)
    }
    if (typeof body.code === 'string') {
      code = body.code
    }
  } catch {
    /* ignore */
  }
  return new ApiError(response.status, detail, code)
}

export async function patchSalonProfile(
  token: string,
  salonId: string,
  body: SalonProfilePatch,
): Promise<SalonProfile> {
  const response = await fetch(`/api/v1/salons/${salonId}/profile`, {
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
  return (await response.json()) as SalonProfile
}
