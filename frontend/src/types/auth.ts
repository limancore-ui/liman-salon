export type LoginResponse = {
  access_token: string
  token_type: string
  expires_in: number
}

export type MeResponse = {
  user_id: string
  email: string
  full_name: string
}

export type MySalonMembership = {
  salon_id: string
  salon_name: string
  salon_slug: string
  role: string
}

export type MySalonsResponse = {
  items: MySalonMembership[]
}

export type SalonMembershipList = MySalonMembership[]

export type SalonContextResponse = {
  user_id: string
  salon_id: string
  role: string
  email: string
  salon_name: string
  salon_slug: string
  /** Present when auth salon context API includes IANA timezone. */
  timezone?: string
  /** Present when auth salon context API includes ISO 4217 currency. */
  currency_code?: string | null
}

export type AdminSession = {
  token: string
  user: MeResponse
  salon: SalonContextResponse
  salons: SalonMembershipList
}

export type PendingWorkspaceAuth = {
  token: string
  user: MeResponse
  salons: SalonMembershipList
}
