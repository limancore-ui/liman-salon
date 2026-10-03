export type PublicBookingReviewCreateRequest = {
  token: string
  rating: number
  title?: string | null
  body?: string | null
}

export type PublicBookingReviewCreateResponse = {
  review_id: string
  booking_id: string
  status: string
  rating: number
  title: string | null
  body: string | null
  created_at: string
}

export type PublicBookingReviewStatusResponse = {
  review_id: string
  booking_id: string
  status: string
  rating: number
  title: string | null
  body: string | null
  created_at: string
}

export type AdminReviewListItem = {
  id: string
  booking_id: string | null
  customer_display_name: string
  staff_display_name: string | null
  rating: number
  title: string | null
  body: string | null
  status: string
  created_at: string
  published_at: string | null
  moderated_at: string | null
  moderated_by_user_id: string | null
}

export type AdminReviewModerationResponse = {
  review_id: string
  status: string
  moderated_at: string
  moderated_by_user_id: string
  published_at: string | null
}
