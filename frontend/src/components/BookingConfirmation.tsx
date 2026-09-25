import type { PublicBookingCreateResponse } from '../types/publicBooking'
import { formatBookingDateTime } from '../utils/formatTime'

type BookingConfirmationProps = {
  booking: PublicBookingCreateResponse
  onDone: () => void
}

export function BookingConfirmation({
  booking,
  onDone,
}: BookingConfirmationProps) {
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
        освобождён.
      </p>
      <button type="button" className="btn btn--primary btn--block" onClick={onDone}>
        Готово
      </button>
    </section>
  )
}
