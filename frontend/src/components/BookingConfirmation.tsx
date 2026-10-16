import { useCallback, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { t } from '../i18n'
import type { PublicBookingCreateResponse } from '../types/publicBooking'
import { copyTextToClipboard } from '../utils/copyTextToClipboard'
import { formatBookingDateTime } from '../utils/formatTime'
import {
  buildManageDeepLink,
  buildManagePagePath,
  ensureManageSessionFromCreate,
} from '../utils/manageBookingStorage'
import { SalonHeader } from './SalonHeader'

type BookingConfirmationProps = {
  booking: PublicBookingCreateResponse
  slug: string
  timeZone: string
  onDone: () => void
  /** Salon brand already shown by page header; optional for standalone use/tests. */
  salonName?: string
  logoUrl?: string | null
}

export function BookingConfirmation({
  booking,
  slug,
  timeZone,
  onDone,
  salonName,
  logoUrl,
}: BookingConfirmationProps) {
  const navigate = useNavigate()
  const [copyHint, setCopyHint] = useState<string | null>(null)

  const manageDeepLink = useMemo(
    () => buildManageDeepLink(slug, booking.booking_id, booking.manage_token),
    [slug, booking.booking_id, booking.manage_token],
  )

  const handleManage = useCallback(() => {
    ensureManageSessionFromCreate(slug, booking)
    navigate(buildManagePagePath(slug, booking.booking_id))
  }, [navigate, slug, booking])

  const handleCopyLink = useCallback(async () => {
    setCopyHint(null)
    const copied = await copyTextToClipboard(manageDeepLink)
    if (copied) {
      setCopyHint(t('public.confirmation.copySuccess'))
      return
    }
    setCopyHint(t('public.confirmation.copyFailed'))
  }, [manageDeepLink])

  return (
    <section
      className="booking-confirmation"
      aria-label={t('public.confirmation.ariaLabel')}
    >
      {salonName ? (
        <SalonHeader name={salonName} logoUrl={logoUrl} subtitle={null} />
      ) : null}
      <div className="booking-confirmation__success">
        <h2 className="booking-confirmation__title">
          {t('public.confirmation.title')}
        </h2>
        <p className="booking-confirmation__lead">
          {t('public.confirmation.lead')}
        </p>
      </div>

      <dl className="booking-summary__list booking-confirmation__details">
        <div className="booking-summary__row">
          <dt>{t('public.confirmation.start')}</dt>
          <dd>{formatBookingDateTime(booking.service_start, timeZone)}</dd>
        </div>
        <div className="booking-summary__row">
          <dt>{t('public.confirmation.end')}</dt>
          <dd>{formatBookingDateTime(booking.service_end, timeZone)}</dd>
        </div>
        <div className="booking-summary__row">
          <dt>{t('public.confirmation.bookingId')}</dt>
          <dd className="booking-confirmation__booking-id">
            {booking.booking_id}
          </dd>
        </div>
      </dl>

      <div className="booking-confirmation__manage">
        <h3 className="booking-confirmation__manage-title">
          {t('public.confirmation.manageHeading')}
        </h3>
        <p className="booking-confirmation__hint">
          {t('public.confirmation.manageHint')}
        </p>
        <div className="form-field booking-confirmation__link-field">
          <label className="form-field__label" htmlFor="booking-manage-link">
            {t('public.confirmation.linkLabel')}
          </label>
          <input
            id="booking-manage-link"
            type="text"
            className="form-field__input"
            readOnly
            value={manageDeepLink}
            onFocus={(event) => event.currentTarget.select()}
          />
        </div>
        {copyHint ? (
          <p className="booking-confirmation__copy-hint" role="status">
            {copyHint}
          </p>
        ) : null}
        <div className="booking-confirmation__actions">
          <button
            type="button"
            className="btn btn--primary btn--block"
            onClick={handleManage}
          >
            {t('public.confirmation.manageBooking')}
          </button>
          <button
            type="button"
            className="btn btn--secondary btn--block"
            onClick={() => void handleCopyLink()}
          >
            {t('public.confirmation.copyLink')}
          </button>
        </div>
      </div>

      <div className="booking-confirmation__footer">
        <button
          type="button"
          className="btn btn--secondary btn--block"
          onClick={onDone}
        >
          {t('public.confirmation.done')}
        </button>
      </div>
    </section>
  )
}
