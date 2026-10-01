import { ApiError } from './errors'
import type {
  BlockedPeriodCreateBody,
  BlockedPeriodItem,
  BlockedPeriodUpdateBody,
  ListBlockedPeriodsParams,
  ListWorkingHoursParams,
  WorkingHoursCreateBody,
  WorkingHoursItem,
  WorkingHoursUpdateBody,
} from '../types/schedule'

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

function buildWorkingHoursQuery(params: ListWorkingHoursParams): string {
  const search = new URLSearchParams()
  if (params.staff_id !== undefined && params.staff_id !== '') {
    search.set('staff_id', params.staff_id)
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

function buildBlockedPeriodsQuery(params: ListBlockedPeriodsParams): string {
  const search = new URLSearchParams()
  if (params.staff_id !== undefined && params.staff_id !== '') {
    search.set('staff_id', params.staff_id)
  }
  if (params.starts_from !== undefined && params.starts_from !== '') {
    search.set('starts_from', params.starts_from)
  }
  if (params.ends_to !== undefined && params.ends_to !== '') {
    search.set('ends_to', params.ends_to)
  }
  if (params.block_type !== undefined) {
    search.set('block_type', params.block_type)
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

const scheduleBase = (salonId: string) =>
  `/api/v1/salons/${encodeURIComponent(salonId)}/schedule`

export async function fetchWorkingHours(
  token: string,
  salonId: string,
  params: ListWorkingHoursParams = {},
): Promise<WorkingHoursItem[]> {
  const query = buildWorkingHoursQuery(params)
  const response = await fetch(`${scheduleBase(salonId)}/working-hours${query}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as WorkingHoursItem[]
}

export async function createWorkingHours(
  token: string,
  salonId: string,
  body: WorkingHoursCreateBody,
): Promise<WorkingHoursItem> {
  const response = await fetch(`${scheduleBase(salonId)}/working-hours`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as WorkingHoursItem
}

export async function updateWorkingHours(
  token: string,
  salonId: string,
  workingHoursId: string,
  body: WorkingHoursUpdateBody,
): Promise<WorkingHoursItem> {
  const response = await fetch(
    `${scheduleBase(salonId)}/working-hours/${encodeURIComponent(workingHoursId)}`,
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
  return (await response.json()) as WorkingHoursItem
}

export async function deleteWorkingHours(
  token: string,
  salonId: string,
  workingHoursId: string,
): Promise<void> {
  const response = await fetch(
    `${scheduleBase(salonId)}/working-hours/${encodeURIComponent(workingHoursId)}`,
    {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  if (!response.ok) {
    throw await readApiError(response)
  }
}

export async function fetchBlockedPeriods(
  token: string,
  salonId: string,
  params: ListBlockedPeriodsParams = {},
): Promise<BlockedPeriodItem[]> {
  const query = buildBlockedPeriodsQuery(params)
  const response = await fetch(`${scheduleBase(salonId)}/blocked-periods${query}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as BlockedPeriodItem[]
}

export async function createBlockedPeriod(
  token: string,
  salonId: string,
  body: BlockedPeriodCreateBody,
): Promise<BlockedPeriodItem> {
  const response = await fetch(`${scheduleBase(salonId)}/blocked-periods`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as BlockedPeriodItem
}

export async function updateBlockedPeriod(
  token: string,
  salonId: string,
  blockedPeriodId: string,
  body: BlockedPeriodUpdateBody,
): Promise<BlockedPeriodItem> {
  const response = await fetch(
    `${scheduleBase(salonId)}/blocked-periods/${encodeURIComponent(blockedPeriodId)}`,
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
  return (await response.json()) as BlockedPeriodItem
}

export async function deleteBlockedPeriod(
  token: string,
  salonId: string,
  blockedPeriodId: string,
): Promise<void> {
  const response = await fetch(
    `${scheduleBase(salonId)}/blocked-periods/${encodeURIComponent(blockedPeriodId)}`,
    {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  if (!response.ok) {
    throw await readApiError(response)
  }
}
