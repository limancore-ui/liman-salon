/** Matches backend `BlockType` / blocked period `block_type`. */
export type BlockType = 'manual' | 'holiday' | 'time_off'

/** Matches backend `WorkingHoursResponse`. */
export type WorkingHoursItem = {
  id: string
  staff_id: string | null
  day_of_week: number
  start_time: string
  end_time: string
  effective_from: string | null
  effective_to: string | null
  created_at: string
  updated_at: string
}

/** Matches backend `BlockedPeriodResponse`. */
export type BlockedPeriodItem = {
  id: string
  staff_id: string | null
  starts_at: string
  ends_at: string
  reason: string | null
  block_type: string
  created_by_user_id: string | null
  created_at: string
  updated_at: string
}

export type ListWorkingHoursParams = {
  staff_id?: string
}

export type ListBlockedPeriodsParams = {
  staff_id?: string
  starts_from?: string
  ends_to?: string
  block_type?: BlockType
}

/** Matches backend `BlockedPeriodCreateRequest`. */
export type BlockedPeriodCreateBody = {
  staff_id?: string | null
  starts_at: string
  ends_at: string
  reason?: string | null
  block_type?: BlockType
}

/** Matches backend `BlockedPeriodUpdateRequest`. */
export type BlockedPeriodUpdateBody = {
  staff_id?: string | null
  starts_at?: string
  ends_at?: string
  reason?: string | null
  block_type?: BlockType
}
