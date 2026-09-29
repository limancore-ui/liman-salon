import type { PublicSelectedSlot } from '../types/publicSalon'
import { formatServiceStartTime } from '../utils/formatTime'
import { ErrorState } from './ErrorState'
import { LoadingState } from './LoadingState'

export type AvailabilityTimeListState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; slots: PublicSelectedSlot[] }
  | { status: 'error' }

type AvailabilityTimeListProps = {
  state: AvailabilityTimeListState
  selectedSlot: PublicSelectedSlot | null
  onSelectSlot: (slot: PublicSelectedSlot) => void
}

function slotKey(slot: PublicSelectedSlot): string {
  return `${slot.staff_id}|${slot.service_start}|${slot.service_end}`
}

export function AvailabilityTimeList({
  state,
  selectedSlot,
  onSelectSlot,
}: AvailabilityTimeListProps) {
  if (state.status === 'idle' || state.status === 'loading') {
    return <LoadingState message="Загрузка времени…" />
  }

  if (state.status === 'error') {
    return (
      <ErrorState
        title="Не удалось загрузить время"
        message="Попробуйте выбрать другую дату или повторить позже."
      />
    )
  }

  if (state.slots.length === 0) {
    return (
      <p className="time-list__empty">На выбранную дату свободного времени нет.</p>
    )
  }

  const selectedKey = selectedSlot ? slotKey(selectedSlot) : null

  return (
    <div className="time-list">
      <h3 className="time-list__heading">Выберите время</h3>
      <ul className="time-list__grid" role="listbox" aria-label="Выберите время">
        {state.slots.map((slot) => {
          const key = slotKey(slot)
          const selected = key === selectedKey
          return (
            <li key={key} className="time-list__item">
              <button
                type="button"
                role="option"
                aria-selected={selected}
                className={`time-slot${selected ? ' time-slot--selected' : ''}`}
                onClick={() => onSelectSlot(slot)}
              >
                {formatServiceStartTime(slot.service_start)}
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
