import { ApiError } from './errors'
import type {
  AdminDashboardSnapshot,
  DashboardStatusCounts,
} from '../types/dashboard'

const EMPTY_STATUS_COUNTS: DashboardStatusCounts = {
  pending: 0,
  confirmed: 0,
  in_progress: 0,
  completed: 0,
  cancelled: 0,
  no_show: 0,
  expired: 0,
}

function normalizeStatusCounts(
  raw: Partial<DashboardStatusCounts> | undefined,
): DashboardStatusCounts {
  if (!raw) {
    return { ...EMPTY_STATUS_COUNTS }
  }
  return {
    pending: raw.pending ?? 0,
    confirmed: raw.confirmed ?? 0,
    in_progress: raw.in_progress ?? 0,
    completed: raw.completed ?? 0,
    cancelled: raw.cancelled ?? 0,
    no_show: raw.no_show ?? 0,
    expired: raw.expired ?? 0,
  }
}

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

export async function fetchAdminDashboard(
  token: string,
  salonId: string,
): Promise<AdminDashboardSnapshot> {
  const response = await fetch(
    `/api/v1/salons/${encodeURIComponent(salonId)}/dashboard`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  if (!response.ok) {
    throw await readApiError(response)
  }
  const body = (await response.json()) as AdminDashboardSnapshot
  return {
    ...body,
    status_counts: normalizeStatusCounts(body.status_counts),
    attention_bookings: Array.isArray(body.attention_bookings)
      ? body.attention_bookings
      : [],
  }
}
