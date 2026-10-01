import { formatPrice } from './format'

export function formatBookingTime(iso: string, timeZone: string | undefined): string {
  const date = new Date(iso)
  if (timeZone) {
    return date.toLocaleTimeString(undefined, { timeStyle: 'short', timeZone })
  }
  return date.toLocaleTimeString(undefined, { timeStyle: 'short', timeZone: 'UTC' }) + ' UTC'
}

export function formatBookingDateTime(iso: string, timeZone: string | undefined): string {
  const date = new Date(iso)
  if (timeZone) {
    return date.toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone,
    })
  }
  return (
    date.toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone: 'UTC',
    }) + ' UTC'
  )
}

export function formatDashboardPrice(
  cents: number,
  currencyCode: string | null | undefined,
): string {
  if (currencyCode) {
    return formatPrice(cents, currencyCode)
  }
  const amount = cents / 100
  return amount.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}
