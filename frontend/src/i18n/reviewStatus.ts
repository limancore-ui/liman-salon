import { t, type MessageKey } from './index'

const REVIEW_STATUS_LABEL_KEYS: Record<string, MessageKey> = {
  pending: 'admin.reviews.status.pending',
  published: 'admin.reviews.status.published',
  rejected: 'admin.reviews.status.rejected',
  hidden: 'admin.reviews.status.hidden',
}

/** Display label for a review status API value. Unknown codes fall back safely. */
export function reviewStatusLabel(status: string): string {
  const key = REVIEW_STATUS_LABEL_KEYS[status]
  if (key) {
    return t(key)
  }
  return status.replaceAll('_', ' ')
}
