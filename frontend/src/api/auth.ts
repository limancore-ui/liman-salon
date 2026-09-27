import { ApiError } from './errors'
import type {
  LoginResponse,
  MeResponse,
  SalonContextResponse,
} from '../types/auth'

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

async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as T
}

export async function loginWithPassword(
  email: string,
  password: string,
): Promise<LoginResponse> {
  let response: Response
  try {
    response = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
  } catch {
    throw new ApiError(0, 'network error')
  }
  return parseJsonResponse<LoginResponse>(response)
}

export async function fetchCurrentUser(token: string): Promise<MeResponse> {
  const response = await fetch('/api/v1/auth/me', {
    headers: { Authorization: `Bearer ${token}` },
  })
  return parseJsonResponse<MeResponse>(response)
}

export async function fetchSalonContext(
  token: string,
  salonId: string,
): Promise<SalonContextResponse> {
  const response = await fetch(
    `/api/v1/auth/salons/${encodeURIComponent(salonId)}/context`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  return parseJsonResponse<SalonContextResponse>(response)
}

export function isUnauthorizedError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401
}
