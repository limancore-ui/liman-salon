import type { PublicCatalogStaffOut } from '../types/publicCatalog'
import { ErrorState } from './ErrorState'
import { LoadingState } from './LoadingState'

export type ServiceStaffListState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; staff: PublicCatalogStaffOut[] }
  | { status: 'error'; message: string }

type ServiceStaffListProps = {
  state: ServiceStaffListState
  selectedStaffId: string | null
  onSelectStaff: (staff: PublicCatalogStaffOut) => void
}

export function ServiceStaffList({
  state,
  selectedStaffId,
  onSelectStaff,
}: ServiceStaffListProps) {
  if (state.status === 'idle' || state.status === 'loading') {
    return <LoadingState message="Загрузка мастеров…" />
  }

  if (state.status === 'error') {
    return (
      <ErrorState
        title="Не удалось загрузить мастеров"
        message={state.message}
      />
    )
  }

  if (state.staff.length === 0) {
    return (
      <p className="staff-list__empty">Нет доступных мастеров для этой услуги.</p>
    )
  }

  return (
    <ul className="staff-list" role="listbox" aria-label="Выберите мастера">
      {state.staff.map((member) => {
        const selected = member.id === selectedStaffId
        return (
          <li key={member.id} className="staff-list__item">
            <button
              type="button"
              role="option"
              aria-selected={selected}
              className={`staff-card${selected ? ' staff-card--selected' : ''}`}
              onClick={() => onSelectStaff(member)}
            >
              <span className="staff-card__name">{member.display_name}</span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
