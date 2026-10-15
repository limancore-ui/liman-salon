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

/** Proposal fields shared with the impact preview. Times are wall-clock `HH:mm:ss`. */
export type WorkingHoursCreateProposal = {
  staff_id?: string | null
  day_of_week: number
  start_time: string
  end_time: string
  effective_from?: string | null
  effective_to?: string | null
}

/** Matches backend `WorkingHoursCreateRequest` (proposal plus commit gate). */
export type WorkingHoursCreateBody = WorkingHoursCreateProposal & {
  impact_fingerprint: string
  as_of: string
  horizon_days: number
  acknowledge_impacts: boolean
}

/** Matches backend `WorkingHoursDeleteRequest`. */
export type WorkingHoursDeleteBody = {
  impact_fingerprint: string
  as_of: string
  horizon_days: number
  acknowledge_impacts: boolean
}

/** Matches backend `WorkingHoursUpdateRequest`. */
export type WorkingHoursUpdateBody = {
  staff_id?: string | null
  day_of_week?: number
  start_time?: string
  end_time?: string
  effective_from?: string | null
  effective_to?: string | null
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

/** Backend defaults / bounds (`app.services.schedule.impact`). */
export const SCHEDULE_IMPACT_DEFAULT_HORIZON_DAYS = 90
export const SCHEDULE_IMPACT_MAX_HORIZON_DAYS = 365
export const SCHEDULE_IMPACT_DEFAULT_LIMIT = 50
export const SCHEDULE_IMPACT_MAX_LIMIT = 100

/** Discriminated union matching backend `ScheduleImpactChangeRequest`. */
export type WorkingHoursCreateImpactChange = WorkingHoursCreateProposal & {
  kind: 'working_hours.create'
}

export type WorkingHoursUpdateImpactChange = WorkingHoursUpdateBody & {
  kind: 'working_hours.update'
  working_hours_id: string
}

export type WorkingHoursDeleteImpactChange = {
  kind: 'working_hours.delete'
  working_hours_id: string
}

export type BlockedPeriodCreateImpactChange = BlockedPeriodCreateBody & {
  kind: 'blocked_period.create'
}

export type BlockedPeriodUpdateImpactChange = BlockedPeriodUpdateBody & {
  kind: 'blocked_period.update'
  blocked_period_id: string
}

export type BlockedPeriodDeleteImpactChange = {
  kind: 'blocked_period.delete'
  blocked_period_id: string
}

export type StaffServiceDetachImpactChange = {
  kind: 'staff_service.detach'
  staff_id: string
  service_id: string
}

export type ScheduleImpactChange =
  | WorkingHoursCreateImpactChange
  | WorkingHoursUpdateImpactChange
  | WorkingHoursDeleteImpactChange
  | BlockedPeriodCreateImpactChange
  | BlockedPeriodUpdateImpactChange
  | BlockedPeriodDeleteImpactChange
  | StaffServiceDetachImpactChange

/** Matches backend `ScheduleImpactPreviewRequest`. */
export type ScheduleImpactPreviewRequestBody = {
  change: ScheduleImpactChange
  horizon_days?: number
  impact_offset?: number
  impact_limit?: number
}

/** Matches backend `ImpactHorizonSummary`. */
export type ImpactHorizonSummary = {
  starts_at_from: string
  starts_at_to: string
  days: number
}

/** Matches backend `ScheduleImpactChangeSummary`. */
export type ScheduleImpactChangeSummary = {
  kind: string
  affected_staff_ids: string[]
  horizon: ImpactHorizonSummary
}

/** Matches backend `ScheduleImpactBookingRow`. */
export type ScheduleImpactBookingRow = {
  booking_id: string
  status: string
  is_in_progress: boolean
  starts_at: string
  ends_at: string
  staff_id: string
  service_id: string
  customer_name: string
  service_name: string
  reasons: string[]
}

/** Matches backend `ScheduleImpactCounts`. */
export type ScheduleImpactCounts = {
  total_impacted: number
  by_reason: Record<string, number>
}

/** Matches backend `ScheduleImpactPagination`. */
export type ScheduleImpactPagination = {
  offset: number
  limit: number
  returned: number
  total_impacted: number
  has_more: boolean
}

/** Matches backend `ScheduleImpactCommitPolicy`. */
export type ScheduleImpactCommitPolicy = {
  allow_commit_with_impacts: boolean
  requires_acknowledgement: boolean
}

/** Matches backend `ScheduleImpactPreviewResponse`. */
export type ScheduleImpactPreviewResponse = {
  as_of: string
  change_summary: ScheduleImpactChangeSummary
  impacts: ScheduleImpactBookingRow[]
  counts: ScheduleImpactCounts
  pagination: ScheduleImpactPagination
  commit_policy: ScheduleImpactCommitPolicy
  impact_fingerprint: string
}
