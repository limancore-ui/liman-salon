/** Matches backend `ImpactReason` (`types_impact.py`). */
export type ScheduleImpactReasonCode =
  | 'outside_availability'
  | 'staff_no_longer_performs_service'

const REASON_LABELS: Record<
  ScheduleImpactReasonCode,
  { en: string; ru: string }
> = {
  outside_availability: {
    en: 'Outside available hours or blocked time',
    ru: 'Вне доступного времени или в заблокированном интервале',
  },
  staff_no_longer_performs_service: {
    en: 'Staff member no longer performs this service',
    ru: 'Сотрудник больше не выполняет эту услугу',
  },
}

export function isScheduleImpactReasonCode(
  code: string,
): code is ScheduleImpactReasonCode {
  return code === 'outside_availability' || code === 'staff_no_longer_performs_service'
}

export type ScheduleImpactReasonLocale = 'en' | 'ru'

/** User-facing label for a backend impact reason code. Unknown codes are returned as-is. */
export function formatScheduleImpactReason(
  code: string,
  locale: ScheduleImpactReasonLocale = 'ru',
): string {
  if (!isScheduleImpactReasonCode(code)) {
    return code
  }
  return REASON_LABELS[code][locale]
}

/** Format all reason codes on an impact row (deduplicated, stable order). */
export function formatScheduleImpactReasons(
  reasons: string[],
  locale: ScheduleImpactReasonLocale = 'ru',
): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const code of reasons) {
    if (seen.has(code)) {
      continue
    }
    seen.add(code)
    out.push(formatScheduleImpactReason(code, locale))
  }
  return out
}
