export type SalonBookingSettings = {
  public_hold_seconds: number
}

export type SalonSettings = {
  v: 1
  booking?: SalonBookingSettings | null
}

export type SalonSettingsPatch = {
  booking?:
    | {
        public_hold_seconds: number
      }
    | null
}
