import type {
  ScheduleImpactBookingRow,
  ScheduleImpactChange,
  ScheduleImpactPreviewResponse,
} from '../types/schedule'
import { useScheduleImpactPreview } from '../hooks/useScheduleImpactPreview'
import { t, bookingStatusLabel } from '../i18n'
import { formatScheduleImpactReasons } from '../utils/mapScheduleImpactReason'
import { isScheduleImpactConfirmDisabled } from '../utils/scheduleImpactPreviewState'

const PREVIEW_LOCALE = 'ru' as const

function formatPreviewDateTime(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

export type ScheduleImpactPreviewConfirmPayload = {
  impacts: ScheduleImpactBookingRow[]
  /** First-page preview. Load-more does not replace this response. */
  response: ScheduleImpactPreviewResponse
  fingerprint: string
  change: ScheduleImpactChange
  acknowledgementChecked: boolean
}

export type ScheduleImpactPreviewPanelProps = {
  token: string
  salonId: string
  change: ScheduleImpactChange
  onCancel: () => void
  onConfirm: (payload: ScheduleImpactPreviewConfirmPayload) => void
  confirmLabel?: string
  horizonDays?: number
  impactLimit?: number
}

export type ScheduleImpactPreviewViewProps = {
  loading: boolean
  loadingMore: boolean
  error: string | null
  loadMoreError: string | null
  response: ScheduleImpactPreviewResponse | null
  impacts: ScheduleImpactBookingRow[]
  acknowledgementChecked: boolean
  onAcknowledgementChange: (checked: boolean) => void
  confirmDisabled: boolean
  canLoadMore: boolean
  onRetry: () => void
  onLoadMore: () => void
  onCancel: () => void
  onConfirm: () => void
  confirmLabel: string
}

export function ScheduleImpactPreviewView({
  loading,
  loadingMore,
  error,
  loadMoreError,
  response,
  impacts,
  acknowledgementChecked,
  onAcknowledgementChange,
  confirmDisabled,
  canLoadMore,
  onRetry,
  onLoadMore,
  onCancel,
  onConfirm,
  confirmLabel,
}: ScheduleImpactPreviewViewProps) {
  const titleId = 'schedule-impact-preview-title'
  const totalImpacted = response?.counts.total_impacted ?? 0
  const requiresAck = response?.commit_policy.requires_acknowledgement ?? false
  const bookingWord =
    totalImpacted === 1
      ? t('admin.impact.bookingSingular')
      : t('admin.impact.bookingPlural')

  return (
    <section
      className="schedule-impact-preview"
      aria-labelledby={titleId}
      aria-busy={loading || loadingMore}
    >
      <header className="schedule-impact-preview__header">
        <h2 id={titleId} className="schedule-impact-preview__title">
          {t('admin.impact.title')}
        </h2>
        <p className="schedule-impact-preview__lead">{t('admin.impact.lead')}</p>
      </header>

      {loading ? (
        <p className="schedule-impact-preview__state" role="status">
          {t('admin.impact.loading')}
        </p>
      ) : null}

      {!loading && error ? (
        <div className="schedule-impact-preview__state schedule-impact-preview__state--error">
          <p role="alert">{error}</p>
          <button
            type="button"
            className="btn btn--secondary btn--compact"
            onClick={onRetry}
          >
            {t('admin.impact.retry')}
          </button>
        </div>
      ) : null}

      {!loading && !error && response ? (
        <>
          <div className="schedule-impact-preview__summary">
            <p>
              <strong>{totalImpacted}</strong> {bookingWord}{' '}
              {t('admin.impact.mayBeAffected')}
              {response.change_summary.horizon.days > 0
                ? ` ${t('admin.impact.nextDays', {
                    days: String(response.change_summary.horizon.days),
                  })}`
                : ''}
              .
            </p>
            <p className="schedule-impact-preview__as-of">
              {t('admin.impact.asOf', {
                when: formatPreviewDateTime(response.as_of),
              })}
            </p>
          </div>

          {totalImpacted === 0 ? (
            <p className="schedule-impact-preview__state" role="status">
              {t('admin.impact.noneAffectedLong')}
            </p>
          ) : (
            <>
              <p className="schedule-impact-preview__showing">
                {t('admin.impact.showingPrefix')} {impacts.length}{' '}
                {t('admin.impact.showingOf')} {totalImpacted}{' '}
                {t('admin.impact.affected')} {bookingWord}.
              </p>
              <ul className="schedule-impact-preview__list">
                {impacts.map((row) => {
                  const reasonLabels = formatScheduleImpactReasons(
                    row.reasons,
                    PREVIEW_LOCALE,
                  )
                  return (
                    <li
                      key={row.booking_id}
                      className="schedule-impact-preview__item"
                    >
                      <article className="schedule-impact-preview__card">
                        <h3 className="schedule-impact-preview__customer">
                          {row.customer_name}
                        </h3>
                        <dl className="schedule-impact-preview__details">
                          <div>
                            <dt>{t('admin.impact.service')}</dt>
                            <dd>{row.service_name}</dd>
                          </div>
                          <div>
                            <dt>{t('admin.impact.start')}</dt>
                            <dd>{formatPreviewDateTime(row.starts_at)}</dd>
                          </div>
                          <div>
                            <dt>{t('admin.impact.end')}</dt>
                            <dd>{formatPreviewDateTime(row.ends_at)}</dd>
                          </div>
                          <div>
                            <dt>{t('common.status')}</dt>
                            <dd>
                              {bookingStatusLabel(row.status)}
                              {row.is_in_progress ? (
                                <span className="schedule-impact-preview__badge">
                                  {t('admin.status.inProgress')}
                                </span>
                              ) : null}
                            </dd>
                          </div>
                          {reasonLabels.length > 0 ? (
                            <div>
                              <dt>{t('admin.impact.reasons')}</dt>
                              <dd>
                                <ul className="schedule-impact-preview__reasons">
                                  {reasonLabels.map((label) => (
                                    <li key={label}>{label}</li>
                                  ))}
                                </ul>
                              </dd>
                            </div>
                          ) : null}
                        </dl>
                      </article>
                    </li>
                  )
                })}
              </ul>
              {loadMoreError ? (
                <div
                  className="schedule-impact-preview__state schedule-impact-preview__state--error schedule-impact-preview__load-more-error"
                  role="alert"
                >
                  <p>{loadMoreError}</p>
                </div>
              ) : null}
              {canLoadMore ? (
                <button
                  type="button"
                  className="btn btn--secondary btn--compact schedule-impact-preview__load-more"
                  onClick={onLoadMore}
                  disabled={loadingMore}
                  aria-busy={loadingMore}
                >
                  {loadingMore
                    ? t('admin.impact.loadingMore')
                    : t('admin.impact.loadMore')}
                </button>
              ) : null}
            </>
          )}

          {requiresAck && totalImpacted > 0 ? (
            <label className="schedule-impact-preview__ack">
              <input
                type="checkbox"
                checked={acknowledgementChecked}
                onChange={(event) =>
                  onAcknowledgementChange(event.target.checked)
                }
              />
              <span>
                {t('admin.impact.ackPrefix')} {totalImpacted}{' '}
                {totalImpacted === 1
                  ? t('admin.impact.ackMaySingular')
                  : t('admin.impact.ackMayPlural')}
              </span>
            </label>
          ) : null}
        </>
      ) : null}

      <div className="schedule-impact-preview__actions">
        <button
          type="button"
          className="btn btn--secondary btn--compact"
          onClick={onCancel}
        >
          {t('common.cancel')}
        </button>
        <button
          type="button"
          className="btn btn--primary btn--compact"
          onClick={onConfirm}
          disabled={confirmDisabled}
        >
          {confirmLabel}
        </button>
      </div>
    </section>
  )
}

export function ScheduleImpactPreviewPanel({
  token,
  salonId,
  change,
  onCancel,
  onConfirm,
  confirmLabel = t('admin.impact.continue'),
  horizonDays,
  impactLimit,
}: ScheduleImpactPreviewPanelProps) {
  const preview = useScheduleImpactPreview({
    token,
    salonId,
    change,
    horizonDays,
    impactLimit,
  })

  const requiresAcknowledgement =
    preview.response?.commit_policy.requires_acknowledgement ?? false

  const confirmDisabled = isScheduleImpactConfirmDisabled({
    loading: preview.loading,
    loadingMore: preview.loadingMore,
    error: preview.error,
    hasResponse: preview.canonicalResponse !== null,
    requiresAcknowledgement,
    acknowledgementChecked: preview.acknowledgementChecked,
  })

  function handleConfirm() {
    if (
      confirmDisabled ||
      !preview.canonicalResponse ||
      !preview.fingerprint
    ) {
      return
    }
    onConfirm({
      impacts: preview.impacts,
      response: preview.canonicalResponse,
      fingerprint: preview.fingerprint,
      change,
      acknowledgementChecked: preview.acknowledgementChecked,
    })
  }

  return (
    <ScheduleImpactPreviewView
      loading={preview.loading}
      loadingMore={preview.loadingMore}
      error={preview.error}
      loadMoreError={preview.loadMoreError}
      response={preview.response}
      impacts={preview.impacts}
      acknowledgementChecked={preview.acknowledgementChecked}
      onAcknowledgementChange={preview.setAcknowledgementChecked}
      confirmDisabled={confirmDisabled}
      canLoadMore={preview.canLoadMore}
      onRetry={preview.retry}
      onLoadMore={preview.loadMore}
      onCancel={onCancel}
      onConfirm={handleConfirm}
      confirmLabel={confirmLabel}
    />
  )
}
