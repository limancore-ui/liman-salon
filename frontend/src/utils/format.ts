export function formatPrice(priceCents: number, currencyCode: string): string {
  const amount = priceCents / 100
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency: currencyCode,
    }).format(amount)
  } catch {
    return `${amount.toFixed(2)} ${currencyCode}`
  }
}

export function formatDuration(durationMinutes: number): string {
  return `${durationMinutes} min`
}
