import { ApiError } from './errors'
import type {
  AdminNotificationItem,
  AdminNotificationList,
  AdminNotificationStreamPayload,
} from '../types/adminNotifications'

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

export async function fetchAdminNotifications(
  token: string,
  salonId: string,
  options?: { limit?: number; offset?: number },
): Promise<AdminNotificationList> {
  const params = new URLSearchParams()
  if (options?.limit != null) {
    params.set('limit', String(options.limit))
  }
  if (options?.offset != null) {
    params.set('offset', String(options.offset))
  }
  const qs = params.toString()
  const response = await fetch(
    `/api/v1/salons/${encodeURIComponent(salonId)}/admin-notifications${qs ? `?${qs}` : ''}`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  if (!response.ok) {
    throw await readApiError(response)
  }
  const body = (await response.json()) as AdminNotificationList
  return {
    items: Array.isArray(body.items) ? body.items : [],
    unread_count: body.unread_count ?? 0,
  }
}

export async function markAdminNotificationRead(
  token: string,
  salonId: string,
  notificationId: string,
): Promise<void> {
  const response = await fetch(
    `/api/v1/salons/${encodeURIComponent(salonId)}/admin-notifications/${encodeURIComponent(notificationId)}/read`,
    {
      method: 'PATCH',
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  if (!response.ok && response.status !== 204) {
    throw await readApiError(response)
  }
}

export async function markAllAdminNotificationsRead(
  token: string,
  salonId: string,
): Promise<number> {
  const response = await fetch(
    `/api/v1/salons/${encodeURIComponent(salonId)}/admin-notifications/mark-all-read`,
    {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  if (!response.ok) {
    throw await readApiError(response)
  }
  const body = (await response.json()) as { marked_count?: number }
  return body.marked_count ?? 0
}

export type AdminNotificationStreamHandlers = {
  onNotification: (item: AdminNotificationItem) => void
  onError?: (error: Error) => void
}

/**
 * SSE over fetch so Authorization bearer header is supported (unlike EventSource).
 */
export async function subscribeAdminNotificationStream(
  token: string,
  salonId: string,
  afterId: string | null,
  handlers: AdminNotificationStreamHandlers,
  signal: AbortSignal,
): Promise<void> {
  const params = new URLSearchParams()
  if (afterId) {
    params.set('after_id', afterId)
  }
  const qs = params.toString()
  const response = await fetch(
    `/api/v1/salons/${encodeURIComponent(salonId)}/admin-notifications/stream${qs ? `?${qs}` : ''}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'text/event-stream',
      },
      signal,
    },
  )
  if (!response.ok) {
    throw await readApiError(response)
  }
  if (!response.body) {
    throw new Error('notification stream unavailable')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''
    for (const part of parts) {
      const line = part
        .split('\n')
        .find((l) => l.startsWith('data: '))
      if (!line) {
        continue
      }
      try {
        const payload = JSON.parse(
          line.slice(6),
        ) as AdminNotificationStreamPayload
        if (payload.notification) {
          handlers.onNotification(payload.notification)
        }
      } catch (err) {
        handlers.onError?.(
          err instanceof Error ? err : new Error('invalid stream payload'),
        )
      }
    }
  }
}
