/** Matches backend `ServiceResponse`. */
export type ServiceListItem = {
  id: string
  name: string
  description: string | null
  duration_minutes: number
  buffer_before_minutes: number
  buffer_after_minutes: number
  price_cents: number
  is_active: boolean
  sort_order: number
  currency_code: string | null
  created_at: string
  updated_at: string
}

export type ListServicesParams = {
  active_only?: boolean
}

/** Matches backend `ServiceCreateRequest`. */
export type ServiceCreateBody = {
  name: string
  description?: string | null
  duration_minutes?: number
  buffer_before_minutes?: number
  buffer_after_minutes?: number
  price_cents?: number
  is_active?: boolean
  sort_order?: number
}

/** Matches backend `ServiceUpdateRequest`. */
export type ServiceUpdateBody = {
  name?: string
  description?: string | null
  duration_minutes?: number
  buffer_before_minutes?: number
  buffer_after_minutes?: number
  price_cents?: number
  is_active?: boolean
  sort_order?: number
}
