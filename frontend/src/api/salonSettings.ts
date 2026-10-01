import { ApiError } from './errors'
import type { SalonSettings, SalonSettingsPatch } from '../types/salonSettings'

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
    /* ignore non-JSON error bodies */
  }
  return new ApiError(response.status, detail, code)
}

export async function fetchSalonSettings(
  token: string,
  salonId: string,
): Promise<SalonSettings> {
  const response = await fetch(
    `/api/v1/salons/${encodeURIComponent(salonId)}/settings`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as SalonSettings
}

export async function patchSalonSettings(
  token: string,
  salonId: string,
  body: SalonSettingsPatch,
): Promise<SalonSettings> {
  const response = await fetch(
    `/api/v1/salons/${encodeURIComponent(salonId)}/settings`,
    {
      method: 'PATCH',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    },
  )
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as SalonSettings
}
