import type { PublicCatalogServiceWithMedia } from '../types/publicCatalog'
import { formatDuration, formatPrice } from '../utils/format'

type SelectedServiceBarProps = {
  service: PublicCatalogServiceWithMedia
}

export function SelectedServiceBar({ service }: SelectedServiceBarProps) {
  return (
    <div className="selected-service-bar" aria-label="Выбранная услуга">
      <p className="selected-service-bar__name">{service.name}</p>
      <p className="selected-service-bar__meta">
        <span className="selected-service-bar__price">
          {formatPrice(service.price_cents, service.currency_code)}
        </span>
        <span className="selected-service-bar__sep" aria-hidden="true">
          ·
        </span>
        <span className="selected-service-bar__duration">
          {formatDuration(service.duration_minutes)}
        </span>
      </p>
    </div>
  )
}
