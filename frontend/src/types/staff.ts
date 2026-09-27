/** Matches backend `StaffResponse`. */
export type StaffListItem = {
  id: string
  display_name: string
  title: string | null
  bio: string | null
  color_hex: string | null
  is_bookable: boolean
  is_active: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

export type ListStaffParams = {
  active_only?: boolean
  bookable_only?: boolean
}
