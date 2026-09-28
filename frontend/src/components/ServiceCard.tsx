import type { PublicCatalogServiceWithMedia } from '../types/publicCatalog'
import { formatDuration, formatPrice } from '../utils/format'
import { PublicImage } from './PublicImage'

type ServiceCardProps = {
  service: PublicCatalogServiceWithMedia
  selected?: boolean
  onSelect?: () => void
}

export function ServiceCard({ service, selected = false, onSelect }: ServiceCardProps) {
  const className = `service-card${selected ? ' service-card--selected' : ''}`

  const content = (
    <>
      <PublicImage
        src={service.cover_url}
        alt=""
        className="service-card__cover"
      />
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
    </>
  )

  if (onSelect) {
    return (
      <button
        type="button"
        className={`${className} service-card--interactive`}
        aria-pressed={selected}
        onClick={onSelect}
      >
        {content}
      </button>
    )
  }

  return <article className={className}>{content}</article>
}
