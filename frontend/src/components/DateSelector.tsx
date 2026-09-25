import { upcomingLocalDates } from '../utils/date'
import { formatDateChipLabel } from '../utils/formatTime'

const DATE_STRIP_DAYS = 14

type DateSelectorProps = {
  selectedDate: string
  onSelectDate: (isoDate: string) => void
}

export function DateSelector({ selectedDate, onSelectDate }: DateSelectorProps) {
  const dates = upcomingLocalDates(DATE_STRIP_DAYS)

  return (
    <div className="date-selector">
      <h3 className="date-selector__heading">Выберите дату</h3>
      <div className="date-selector__strip" role="listbox" aria-label="Выберите дату">
        {dates.map((isoDate) => {
          const selected = isoDate === selectedDate
          return (
            <button
              key={isoDate}
              type="button"
              role="option"
              aria-selected={selected}
              className={`date-chip${selected ? ' date-chip--selected' : ''}`}
              onClick={() => onSelectDate(isoDate)}
            >
              {formatDateChipLabel(isoDate)}
            </button>
          )
        })}
      </div>
    </div>
  )
}
