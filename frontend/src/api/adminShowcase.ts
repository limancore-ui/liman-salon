import { ApiError } from './errors'
import type {
  AdminShowcaseCreateBody,
  AdminShowcaseItem,
  AdminShowcaseListParams,
  AdminShowcasePatchBody,
} from '../types/adminShowcase'

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

function itemCollectionPath(salonId: string): string {
  return `/api/v1/salons/${encodeURIComponent(salonId)}/showcase/items`
}

function itemPath(salonId: string, itemId: string): string {
  return `${itemCollectionPath(salonId)}/${encodeURIComponent(itemId)}`
}

function buildListQuery(params: AdminShowcaseListParams): string {
  const search = new URLSearchParams()
  if (params.limit !== undefined) {
    search.set('limit', String(params.limit))
  }
  if (params.offset !== undefined) {
    search.set('offset', String(params.offset))
  }
  const query = search.toString()
  return query ? `?${query}` : ''
}

function jsonHeaders(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  }
}

export async function fetchAdminShowcaseItems(
  token: string,
  salonId: string,
  params: AdminShowcaseListParams = {},
): Promise<AdminShowcaseItem[]> {
  const response = await fetch(
    `${itemCollectionPath(salonId)}${buildListQuery(params)}`,
    { headers: { Authorization: `Bearer ${token}` } },
  )
  return parseJsonResponse<AdminShowcaseItem[]>(response)
}

export async function createAdminShowcaseItem(
  token: string,
  salonId: string,
  body: AdminShowcaseCreateBody,
): Promise<AdminShowcaseItem> {
  const response = await fetch(itemCollectionPath(salonId), {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(body),
  })
  return parseJsonResponse<AdminShowcaseItem>(response)
}

export async function patchAdminShowcaseItem(
  token: string,
  salonId: string,
  itemId: string,
  body: AdminShowcasePatchBody,
): Promise<AdminShowcaseItem> {
  const response = await fetch(itemPath(salonId, itemId), {
    method: 'PATCH',
    headers: jsonHeaders(token),
    body: JSON.stringify(body),
  })
  return parseJsonResponse<AdminShowcaseItem>(response)
}

async function patchVisibility(
  token: string,
  salonId: string,
  itemId: string,
  action: 'publish' | 'unpublish',
): Promise<AdminShowcaseItem> {
  const response = await fetch(`${itemPath(salonId, itemId)}/${action}`, {
    method: 'PATCH',
    headers: { Authorization: `Bearer ${token}` },
  })
  return parseJsonResponse<AdminShowcaseItem>(response)
}

export function publishAdminShowcaseItem(
  token: string,
  salonId: string,
  itemId: string,
): Promise<AdminShowcaseItem> {
  return patchVisibility(token, salonId, itemId, 'publish')
}

export function unpublishAdminShowcaseItem(
  token: string,
  salonId: string,
  itemId: string,
): Promise<AdminShowcaseItem> {
  return patchVisibility(token, salonId, itemId, 'unpublish')
}

export async function deleteAdminShowcaseItem(
  token: string,
  salonId: string,
  itemId: string,
): Promise<void> {
  const response = await fetch(itemPath(salonId, itemId), {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) {
    throw await readApiError(response)
  }
}
