import { ApiError } from './errors'
import type {
  ListMediaParams,
  MediaAssetDetailResponse,
  MediaAssetResponse,
  MediaAttachRequest,
  MediaAttachmentIndexItem,
  MediaAttachmentResponse,
} from '../types/media'
import { adminMediaContentPath } from '../utils/publicMedia'

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

function buildListQuery(params: ListMediaParams): string {
  const search = new URLSearchParams()
  if (params.limit !== undefined) {
    search.set('limit', String(params.limit))
  }
  if (params.offset !== undefined) {
    search.set('offset', String(params.offset))
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

function mediaBasePath(salonId: string): string {
  return `/api/v1/salons/${encodeURIComponent(salonId)}/media`
}

export async function fetchAdminMediaAttachmentIndex(
  token: string,
  salonId: string,
): Promise<MediaAttachmentIndexItem[]> {
  const response = await fetch(
    `${mediaBasePath(salonId)}/attachments/index`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as MediaAttachmentIndexItem[]
}

export async function fetchAdminMediaList(
  token: string,
  salonId: string,
  params: ListMediaParams = {},
): Promise<MediaAssetResponse[]> {
  const query = buildListQuery(params)
  const response = await fetch(`${mediaBasePath(salonId)}${query}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as MediaAssetResponse[]
}

export async function uploadAdminMedia(
  token: string,
  salonId: string,
  file: File,
): Promise<MediaAssetResponse> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await fetch(mediaBasePath(salonId), {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  })
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as MediaAssetResponse
}

export async function fetchAdminMediaDetail(
  token: string,
  salonId: string,
  mediaId: string,
): Promise<MediaAssetDetailResponse> {
  const response = await fetch(
    `${mediaBasePath(salonId)}/${encodeURIComponent(mediaId)}`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as MediaAssetDetailResponse
}

export async function deleteAdminMedia(
  token: string,
  salonId: string,
  mediaId: string,
): Promise<void> {
  const response = await fetch(
    `${mediaBasePath(salonId)}/${encodeURIComponent(mediaId)}`,
    {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  if (!response.ok) {
    throw await readApiError(response)
  }
}

export async function attachAdminMedia(
  token: string,
  salonId: string,
  mediaId: string,
  body: MediaAttachRequest,
): Promise<MediaAttachmentResponse> {
  const response = await fetch(
    `${mediaBasePath(salonId)}/${encodeURIComponent(mediaId)}/attachments`,
    {
      method: 'PUT',
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
  return (await response.json()) as MediaAttachmentResponse
}

export async function detachAdminMediaAttachment(
  token: string,
  salonId: string,
  mediaId: string,
  attachmentId: string,
): Promise<void> {
  const response = await fetch(
    `${mediaBasePath(salonId)}/${encodeURIComponent(mediaId)}/attachments/${encodeURIComponent(attachmentId)}`,
    {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  if (!response.ok) {
    throw await readApiError(response)
  }
}

export async function fetchAdminMediaContentBlob(
  token: string,
  salonId: string,
  mediaId: string,
): Promise<Blob> {
  const response = await fetch(adminMediaContentPath(salonId, mediaId), {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) {
    throw await readApiError(response)
  }
  return response.blob()
}
