export type AdminShowcaseCategory = 'work' | 'cosmetics' | 'dyes' | 'varnishes'

/** Matches the backend administrative ShowcaseItemResponse. */
export type AdminShowcaseItem = {
  id: string
  salon_id: string
  category: AdminShowcaseCategory
  title: string
  description: string | null
  price_cents: number | null
  media_asset_id: string
  sort_order: number
  is_published: boolean
  created_at: string
  updated_at: string
}

export type AdminShowcaseCreateBody = {
  category: AdminShowcaseCategory
  title: string
  media_asset_id: string
  description?: string | null
  price_cents?: number | null
  sort_order?: number
}

export type AdminShowcasePatchBody = {
  title?: string
  description?: string | null
  category?: AdminShowcaseCategory
  price_cents?: number | null
  media_asset_id?: string
  sort_order?: number
}

export type AdminShowcaseListParams = {
  limit?: number
  offset?: number
}
