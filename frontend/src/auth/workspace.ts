import type { MySalonMembership, SalonMembershipList } from '../types/auth'

export type SalonSelection =
  | { kind: 'none' }
  | { kind: 'picker' }
  | { kind: 'selected'; salonId: string }

export function isSalonIdInMemberships(
  salonId: string,
  memberships: SalonMembershipList,
): boolean {
  return memberships.some((item) => item.salon_id === salonId)
}

/** Choose salon id after /me/salons; hint is stored or dev fallback only. */
export function resolveSalonSelection(
  memberships: SalonMembershipList,
  salonIdHint: string | null,
): SalonSelection {
  if (memberships.length === 0) {
    return { kind: 'none' }
  }
  if (memberships.length === 1) {
    return { kind: 'selected', salonId: memberships[0].salon_id }
  }
  if (salonIdHint && isSalonIdInMemberships(salonIdHint, memberships)) {
    return { kind: 'selected', salonId: salonIdHint }
  }
  return { kind: 'picker' }
}

export function membershipLabel(membership: MySalonMembership): string {
  return `${membership.salon_name} (${membership.salon_slug})`
}
