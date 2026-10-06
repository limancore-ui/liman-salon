export type AdminNotificationItem = {
  id: string
  event_type: string
  booking_id: string
  created_at: string
  read_at: string | null
  booking_starts_at: string
  customer_name: string
  service_name: string
  staff_name: string
}

export type AdminNotificationList = {
  items: AdminNotificationItem[]
  unread_count: number
}

export type AdminNotificationStreamPayload = {
  type: string
  notification: AdminNotificationItem
}
