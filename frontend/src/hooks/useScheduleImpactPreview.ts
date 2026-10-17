import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { previewScheduleImpact } from '../api/schedule'
import type {
  ScheduleImpactChange,
  ScheduleImpactBookingRow,
  ScheduleImpactPreviewResponse,
} from '../types/schedule'
import { adminUserErrorMessage } from '../utils/adminUserError'
import {
  SCHEDULE_IMPACT_DEFAULT_HORIZON_DAYS,
  SCHEDULE_IMPACT_DEFAULT_LIMIT,
} from '../types/schedule'
import {
  buildScheduleImpactDisplayResponse,
  mergeImpactPages,
  paginationFromLoadMorePage,
} from '../utils/scheduleImpactPreviewState'

function mapPreviewError(
  err: unknown,
  fallback: 'admin.error.impactPreviewFailed' | 'admin.error.impactLoadMoreFailed' = 'admin.error.impactPreviewFailed',
): string {
  return adminUserErrorMessage(err, fallback)
}

export type UseScheduleImpactPreviewParams = {
  token: string
  salonId: string
  change: ScheduleImpactChange
  horizonDays?: number
  impactLimit?: number
  /** When false, skip network calls (e.g. panel hidden). Default true. */
  enabled?: boolean
}

export type UseScheduleImpactPreviewResult = {
  loading: boolean
  loadingMore: boolean
  error: string | null
  loadMoreError: string | null
  /** First-page preview for confirm (unchanged by load-more). */
  canonicalResponse: ScheduleImpactPreviewResponse | null
  /** UI view: canonical metadata with pagination updated after load-more. */
  response: ScheduleImpactPreviewResponse | null
  impacts: ScheduleImpactBookingRow[]
  fingerprint: string | null
  acknowledgementChecked: boolean
  setAcknowledgementChecked: (checked: boolean) => void
  retry: () => void
  loadMore: () => void
  canLoadMore: boolean
}

export function useScheduleImpactPreview(
  params: UseScheduleImpactPreviewParams,
): UseScheduleImpactPreviewResult {
  const {
    token,
    salonId,
    change,
    horizonDays = SCHEDULE_IMPACT_DEFAULT_HORIZON_DAYS,
    impactLimit = SCHEDULE_IMPACT_DEFAULT_LIMIT,
    enabled = true,
  } = params

  const changeKey = useMemo(() => JSON.stringify(change), [change])
  const changeRef = useRef(change)
  useEffect(() => {
    changeRef.current = change
  }, [changeKey])

  const horizonDaysStable = horizonDays
  const impactLimitStable = impactLimit

  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loadMoreError, setLoadMoreError] = useState<string | null>(null)
  const [canonicalFirstResponse, setCanonicalFirstResponse] =
    useState<ScheduleImpactPreviewResponse | null>(null)
  const [canonicalFingerprint, setCanonicalFingerprint] = useState<string | null>(
    null,
  )
  const [pagination, setPagination] = useState<
    ScheduleImpactPreviewResponse['pagination'] | null
  >(null)
  const [impacts, setImpacts] = useState<ScheduleImpactBookingRow[]>([])
  const [acknowledgementChecked, setAcknowledgementChecked] = useState(false)

  const requestGeneration = useRef(0)
  const nextRequestId = useRef(0)
  const activeInitialRequestId = useRef(0)
  const activeMoreRequestId = useRef(0)

  const runFetch = useCallback(
    async (offset: number, mode: 'initial' | 'more') => {
      const generation = requestGeneration.current
      const requestId = ++nextRequestId.current
      if (mode === 'initial') {
        activeInitialRequestId.current = requestId
        setLoading(true)
        setError(null)
        setLoadMoreError(null)
      } else {
        activeMoreRequestId.current = requestId
        setLoadingMore(true)
        setLoadMoreError(null)
      }
      try {
        const result = await previewScheduleImpact(token, salonId, {
          change: changeRef.current,
          horizon_days: horizonDaysStable,
          impact_offset: offset,
          impact_limit: impactLimitStable,
        })
        if (generation !== requestGeneration.current) {
          return
        }
        if (mode === 'initial') {
          setCanonicalFirstResponse(result)
          setCanonicalFingerprint(result.impact_fingerprint)
          setPagination(result.pagination)
          setImpacts(result.impacts)
          setAcknowledgementChecked(false)
          setError(null)
          setLoadMoreError(null)
        } else if (activeMoreRequestId.current === requestId) {
          setImpacts((prev) => mergeImpactPages(prev, result.impacts))
          setPagination(paginationFromLoadMorePage(result))
          setLoadMoreError(null)
        }
      } catch (err) {
        if (generation !== requestGeneration.current) {
          return
        }
        if (mode === 'initial') {
          setCanonicalFirstResponse(null)
          setCanonicalFingerprint(null)
          setPagination(null)
          setImpacts([])
          setError(mapPreviewError(err))
        } else if (activeMoreRequestId.current === requestId) {
          setLoadMoreError(mapPreviewError(err, 'admin.error.impactLoadMoreFailed'))
        }
      } finally {
        if (
          mode === 'initial' &&
          activeInitialRequestId.current === requestId
        ) {
          setLoading(false)
        }
        if (
          mode === 'more' &&
          activeMoreRequestId.current === requestId &&
          generation === requestGeneration.current
        ) {
          setLoadingMore(false)
        }
      }
    },
    [token, salonId, horizonDaysStable, impactLimitStable],
  )

  const retry = useCallback(() => {
    requestGeneration.current += 1
    setLoadingMore(false)
    void runFetch(0, 'initial')
  }, [runFetch])

  const loadMore = useCallback(() => {
    if (
      !pagination?.has_more ||
      loading ||
      loadingMore ||
      canonicalFirstResponse === null
    ) {
      return
    }
    const nextOffset = pagination.offset + pagination.returned
    void runFetch(nextOffset, 'more')
  }, [
    pagination,
    loading,
    loadingMore,
    canonicalFirstResponse,
    runFetch,
  ])

  useEffect(() => {
    if (!enabled) {
      return
    }
    requestGeneration.current += 1
    setAcknowledgementChecked(false)
    setCanonicalFirstResponse(null)
    setCanonicalFingerprint(null)
    setPagination(null)
    setImpacts([])
    setError(null)
    setLoadMoreError(null)
    setLoadingMore(false)
    void runFetch(0, 'initial')
  }, [enabled, changeKey, runFetch])

  const response = useMemo(() => {
    if (!canonicalFirstResponse || !pagination) {
      return null
    }
    return buildScheduleImpactDisplayResponse(canonicalFirstResponse, pagination)
  }, [canonicalFirstResponse, pagination])

  const canLoadMore = Boolean(
    pagination?.has_more && !loading && !loadingMore && error === null,
  )

  return {
    loading,
    loadingMore,
    error,
    loadMoreError,
    canonicalResponse: canonicalFirstResponse,
    response,
    impacts,
    fingerprint: canonicalFingerprint,
    acknowledgementChecked,
    setAcknowledgementChecked,
    retry,
    loadMore,
    canLoadMore,
  }
}

