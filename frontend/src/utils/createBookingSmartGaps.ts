import { isoToSalonLocalDatetimeLocal } from './adminBookingTime'
import { formatBookingTime } from './adminSalonFormat'
import type { SmartGapOut } from '../types/smartGaps'

/** Gaps where the selected service appears in suitable_services. */
export function filterSmartGapsForService(
  gaps: SmartGapOut[],
  serviceId: string,
): SmartGapOut[] {
  if (!serviceId) {
    return []
  }
  return gaps.filter((gap) =>
    gap.suitable_services.some((service) => service.service_id === serviceId),
  )
}

/** Map gap.start (UTC ISO) to salon-local value for datetime-local input. */
export function serviceStartFromSmartGap(gapStartIso: string, salonTimeZone: string): string {
  return isoToSalonLocalDatetimeLocal(gapStartIso, salonTimeZone)
}

export function formatSmartGapIntervalLabel(
  gap: SmartGapOut,
  salonTimeZone: string | undefined,
): string {
  const startLabel = formatBookingTime(gap.start, salonTimeZone)
  const endLabel = formatBookingTime(gap.end, salonTimeZone)
  return `${startLabel} – ${endLabel}`
}

export type SmartGapListUiPhase = 'idle' | 'loading' | 'error' | 'empty' | 'ready'

export function deriveSmartGapListPhase(input: {
  loading: boolean
  error: string | null
  searched: boolean
  visibleGapCount: number
}): SmartGapListUiPhase {
  if (input.loading) {
    return 'loading'
  }
  if (input.error) {
    return 'error'
  }
  if (!input.searched) {
    return 'idle'
  }
  if (input.visibleGapCount === 0) {
    return 'empty'
  }
  return 'ready'
}

/** Increment when a search starts or search params change (invalidates in-flight responses). */
export function bumpSmartGapRequestId(currentId: number): number {
  return currentId + 1
}

/** Only apply fetch results / clear loading when this search is still the active one. */
export function shouldApplySmartGapResponse(
  completedRequestId: number,
  activeRequestId: number,
): boolean {
  return completedRequestId === activeRequestId
}

export function smartGapListStatusMessage(
  phase: SmartGapListUiPhase,
  error: string | null,
): string | null {
  switch (phase) {
    case 'loading':
      return 'Loading free gaps…'
    case 'error':
      return error ?? 'Could not load smart gaps.'
    case 'empty':
      return 'No free gaps fit this service on the chosen day.'
    case 'idle':
    case 'ready':
      return null
  }
}
