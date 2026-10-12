import type {
  ScheduleImpactBookingRow,
  ScheduleImpactPagination,
  ScheduleImpactPreviewResponse,
} from '../types/schedule'

/** Append a pagination page without duplicate booking ids. */
export function mergeImpactPages(
  existing: ScheduleImpactBookingRow[],
  page: ScheduleImpactBookingRow[],
): ScheduleImpactBookingRow[] {
  if (page.length === 0) {
    return existing
  }
  const seen = new Set(existing.map((row) => row.booking_id))
  const out = [...existing]
  for (const row of page) {
    if (seen.has(row.booking_id)) {
      continue
    }
    seen.add(row.booking_id)
    out.push(row)
  }
  return out
}

/** Pagination slice from the latest load-more page; canonical fields stay on the first response. */
export function paginationFromLoadMorePage(
  page: ScheduleImpactPreviewResponse,
): ScheduleImpactPagination {
  return page.pagination
}

/** UI / confirm view: first-page metadata with pagination updated after load-more. */
export function buildScheduleImpactDisplayResponse(
  canonicalFirstResponse: ScheduleImpactPreviewResponse,
  pagination: ScheduleImpactPagination,
): ScheduleImpactPreviewResponse {
  return {
    ...canonicalFirstResponse,
    pagination,
  }
}

export function isScheduleImpactConfirmDisabled(params: {
  loading: boolean
  loadingMore: boolean
  error: string | null
  hasResponse: boolean
  requiresAcknowledgement: boolean
  acknowledgementChecked: boolean
}): boolean {
  if (
    params.loading ||
    params.loadingMore ||
    params.error !== null ||
    !params.hasResponse
  ) {
    return true
  }
  if (params.requiresAcknowledgement && !params.acknowledgementChecked) {
    return true
  }
  return false
}

