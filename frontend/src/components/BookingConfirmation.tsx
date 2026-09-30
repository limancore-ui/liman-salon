import { useCallback, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { PublicBookingCreateResponse } from '../types/publicBooking'
import { formatBookingDateTime } from '../utils/formatTime'
import {
  buildManageDeepLink,
  buildManagePagePath,
} from '../utils/manageBookingStorage'

type BookingConfirmationProps = {
  booking: PublicBookingCreateResponse
  slug: string
  onDone: () => void
}

export function BookingConfirmation({
  booking,
  slug,
  onDone,
}: BookingConfirmationProps) {
  const navigate = useNavigate()
  const [copyHint, setCopyHint] = useState<string | null>(null)

  const handleManage = useCallback(() => {
    navigate(buildManagePagePath(slug, booking.booking_id))
  }, [navigate, slug, booking.booking_id])

  const handleCopyLink = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(
        buildManageDeepLink(slug, booking.booking_id, booking.manage_token),
      )
      setCopyHint('Ссылка скопирована')
    } catch {
      setCopyHint('Не удалось скопировать ссылку')
    }
  }, [slug, booking.booking_id, booking.manage_token])

  return (
    <section className="booking-confirmation" aria-label="Запись создана">
      <h2 className="booking-confirmation__title">Запись оформлена</h2>
      <p className="booking-confirmation__lead">
        Заявка принята и ожидает подтверждения салоном.
      </p>
      <dl className="booking-summary__list booking-confirmation__details">
        <div className="booking-summary__row">
          <dt>Начало</dt>
          <dd>{formatBookingDateTime(booking.service_start)}</dd>
        </div>
        <div className="booking-summary__row">
          <dt>Окончание</dt>
          <dd>{formatBookingDateTime(booking.service_end)}</dd>
        </div>
        <div className="booking-summary__row">
          <dt>Номер записи</dt>
          <dd className="booking-confirmation__booking-id">
            {booking.booking_id}
          </dd>
        </div>
        <div className="booking-summary__row">
          <dt>Удержание до</dt>
          <dd>{formatBookingDateTime(booking.hold_expires_at)}</dd>
        </div>
      </dl>
      <p className="booking-confirmation__hint">
        Подтвердите запись до указанного времени, иначе слот может быть
        освобождён. Сохраните ссылку для отмены или переноса записи.
      </p>
      <div className="booking-confirmation__actions">
        <button
          type="button"
          className="btn btn--primary btn--block"
          onClick={handleManage}
        >
          Управлять записью
        </button>
        <button
          type="button"
          className="btn btn--secondary btn--block"
          onClick={() => void handleCopyLink()}
        >
          Скопировать ссылку
        </button>
        {copyHint ? (
          <p className="booking-confirmation__copy-hint" role="status">
            {copyHint}
          </p>
        ) : null}
        <button type="button" className="btn btn--secondary btn--block" onClick={onDone}>
          Готово
        </button>
      </div>
    </section>
  )
}
