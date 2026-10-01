export function formatServiceStartTime(isoUtc: string, timeZone: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone,
  }).format(new Date(isoUtc))
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

export function formatBookingDateTime(isoUtc: string, timeZone: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    hour: '2-digit',
    minute: '2-digit',
    timeZone,
  }).format(new Date(isoUtc))
}
