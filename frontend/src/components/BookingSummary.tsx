import type {
  PublicCatalogServiceOut,
  PublicCatalogStaffOut,
} from '../types/publicCatalog'
import { formatPrice } from '../utils/format'
import { formatDateChipLabel, formatServiceStartTime } from '../utils/formatTime'

type BookingSummaryProps = {
  service: PublicCatalogServiceOut
  staff: PublicCatalogStaffOut
  selectedDate: string
  serviceStartIso: string
}

export function BookingSummary({
  service,
  staff,
  selectedDate,
  serviceStartIso,
}: BookingSummaryProps) {
  return (
    <section className="booking-summary" aria-label="Детали записи">
      <h3 className="booking-summary__heading">Ваша запись</h3>
      <dl className="booking-summary__list">
        <div className="booking-summary__row">
          <dt>Услуга</dt>
          <dd>{service.name}</dd>
        </div>
        <div className="booking-summary__row">
          <dt>Мастер</dt>
          <dd>{staff.display_name}</dd>
        </div>
        <div className="booking-summary__row">
          <dt>Дата</dt>
          <dd>{formatDateChipLabel(selectedDate)}</dd>
        </div>
        <div className="booking-summary__row">
          <dt>Время</dt>
          <dd>{formatServiceStartTime(serviceStartIso)}</dd>
        </div>
        <div className="booking-summary__row">
          <dt>Стоимость</dt>
          <dd>{formatPrice(service.price_cents, service.currency_code)}</dd>
        </div>
      </dl>
    </section>
  )
}
