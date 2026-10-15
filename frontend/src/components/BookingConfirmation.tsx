import { useCallback, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { PublicBookingCreateResponse } from '../types/publicBooking'
import { copyTextToClipboard } from '../utils/copyTextToClipboard'
import { formatBookingDateTime } from '../utils/formatTime'
import {
  buildManageDeepLink,
  buildManagePagePath,
  ensureManageSessionFromCreate,
} from '../utils/manageBookingStorage'

type BookingConfirmationProps = {
  booking: PublicBookingCreateResponse
  slug: string
  timeZone: string
  onDone: () => void
}

export function BookingConfirmation({
  booking,
  slug,
  timeZone,
  onDone,
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
      setCopyHint('Ссылка скопирована')
      return
    }
    setCopyHint('Не удалось скопировать автоматически — выделите ссылку ниже')
  }, [manageDeepLink])

  return (
    <section className="booking-confirmation" aria-label="Запись создана">
      <h2 className="booking-confirmation__title">Запись оформлена</h2>
      <p className="booking-confirmation__lead">
        Заявка принята и ожидает подтверждения салоном.
      </p>
      <dl className="booking-summary__list booking-confirmation__details">
        <div className="booking-summary__row">
          <dt>Начало</dt>
          <dd>{formatBookingDateTime(booking.service_start, timeZone)}</dd>
        </div>
        <div className="booking-summary__row">
          <dt>Окончание</dt>
          <dd>{formatBookingDateTime(booking.service_end, timeZone)}</dd>
        </div>
        <div className="booking-summary__row">
          <dt>Номер записи</dt>
          <dd className="booking-confirmation__booking-id">
            {booking.booking_id}
          </dd>
        </div>
        <div className="booking-summary__row">
          <dt>Удержание до</dt>
          <dd>{formatBookingDateTime(booking.hold_expires_at, timeZone)}</dd>
        </div>
      </dl>
      <p className="booking-confirmation__hint">
        Подтвердите запись до указанного времени, иначе слот может быть
        освобождён. Сохраните ссылку для отмены или переноса записи.
      </p>
      <div className="form-field booking-confirmation__link-field">
        <label className="form-field__label" htmlFor="booking-manage-link">
          Ссылка для управления записью
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
          className="btn btn--secondary btn--block"
          onClick={() => void handleCopyLink()}
        >
          Копировать ссылку
        </button>
        <button
          type="button"
          className="btn btn--primary btn--block"
          onClick={handleManage}
        >
          Управлять записью
        </button>
        <button type="button" className="btn btn--secondary btn--block" onClick={onDone}>
          Готово
        </button>
      </div>
    </section>
  )
}
