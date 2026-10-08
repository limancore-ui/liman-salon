export type SalonBookingSettings = {
  public_hold_seconds: number
}

export type SalonBonusesSettings = {
  enabled: boolean
  earn_percentage: number
}

export type SalonSettings = {
  v: 1
  booking?: SalonBookingSettings | null
  bonuses?: SalonBonusesSettings | null
}

export type SalonSettingsPatch = {
  booking?:
    | {
        public_hold_seconds: number
      }
    | null
  bonuses?:
    | {
        enabled: boolean
        earn_percentage: number
      }
    | null
}
