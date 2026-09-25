import type { PublicCatalogServiceOut } from '../types/publicCatalog'
import { formatDuration, formatPrice } from '../utils/format'

type ServiceCardProps = {
  service: PublicCatalogServiceOut
}

export function ServiceCard({ service }: ServiceCardProps) {
  return (
    <article className="service-card">
      <div className="service-card__header">
        <h2 className="service-card__name">{service.name}</h2>
        <span className="service-card__price">
          {formatPrice(service.price_cents, service.currency_code)}
        </span>
      </div>
      {service.description ? (
        <p className="service-card__description">{service.description}</p>
      ) : null}
      <p className="service-card__meta">
        {formatDuration(service.duration_minutes)}
      </p>
    </article>
  )
}
