/** Matches backend `CustomerResponse`. */
export type CustomerListItem = {
  id: string
  salon_id: string
  user_id: string | null
  full_name: string
  email: string | null
  phone: string | null
  notes: string | null
  bonus_balance_cents: number
  marketing_opt_in: boolean
  whatsapp_opt_in: boolean
  whatsapp_opt_in_at: string | null
  created_at: string
  updated_at: string
}

export type ListCustomersParams = {
  q?: string
  limit?: number
  offset?: number
  sort?: string
}
