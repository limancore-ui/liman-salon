const timeFormatter = new Intl.DateTimeFormat('ru-RU', {
  hour: '2-digit',
  minute: '2-digit',
})

export function formatServiceStartTime(isoUtc: string): string {
  return timeFormatter.format(new Date(isoUtc))
}

const dateChipFormatter = new Intl.DateTimeFormat('ru-RU', {
  weekday: 'short',
  day: 'numeric',
  month: 'short',
})

export function formatDateChipLabel(isoDate: string): string {
  const [y, m, d] = isoDate.split('-').map(Number)
  return dateChipFormatter.format(new Date(y, m - 1, d))
}

const dateTimeFormatter = new Intl.DateTimeFormat('ru-RU', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  hour: '2-digit',
  minute: '2-digit',
})

export function formatBookingDateTime(isoUtc: string): string {
  return dateTimeFormatter.format(new Date(isoUtc))
}
