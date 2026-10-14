export class ApiError extends Error {
  readonly status: number
  readonly code: string | undefined

  constructor(status: number, message: string, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

/** Normalize FastAPI-style error `detail` (string or validation array) for ApiError.message. */
export function formatApiErrorDetail(detail: unknown): string | undefined {
  if (typeof detail === 'string') {
    const trimmed = detail.trim()
    return trimmed === '' ? undefined : trimmed
  }
  if (!Array.isArray(detail)) {
    return undefined
  }
  const messages = detail
    .map((item) => {
      if (item && typeof item === 'object' && 'msg' in item) {
        const msg = (item as { msg?: unknown }).msg
        return typeof msg === 'string' ? msg.trim() : ''
      }
      return ''
    })
    .filter((msg) => msg !== '')
  if (messages.length === 0) {
    return undefined
  }
  return messages.join('; ')
}
