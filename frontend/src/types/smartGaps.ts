export type SuitableServiceOut = {
  service_id: string
  name: string
  duration_minutes: number
  price_cents: number
  bookable_start: string
}

export type SmartGapOut = {
  start: string
  end: string
  suitable_services: SuitableServiceOut[]
}

export type SmartGapListResponse = {
  salon_id: string
  staff_id: string
  gaps: SmartGapOut[]
}

export type FetchSmartGapsParams = {
  staff_id: string
  start_date: string
  end_date: string
}
