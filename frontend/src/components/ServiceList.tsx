import type { PublicCatalogServiceOut } from '../types/publicCatalog'
import { ErrorState } from './ErrorState'
import { LoadingState } from './LoadingState'
import { ServiceCard } from './ServiceCard'

export type ServiceListState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; services: PublicCatalogServiceOut[] }
  | { status: 'error'; message: string }

type ServiceListProps = {
  state: ServiceListState
}

export function ServiceList({ state }: ServiceListProps) {
  if (state.status === 'idle' || state.status === 'loading') {
    return <LoadingState message="Loading services…" />
  }

  if (state.status === 'error') {
    return (
      <ErrorState title="Could not load services" message={state.message} />
    )
  }

  if (state.services.length === 0) {
    return <p className="service-list__empty">No services available yet.</p>
  }

  return (
    <ul className="service-list">
      {state.services.map((service) => (
        <li key={service.id} className="service-list__item">
          <ServiceCard service={service} />
        </li>
      ))}
    </ul>
  )
}
