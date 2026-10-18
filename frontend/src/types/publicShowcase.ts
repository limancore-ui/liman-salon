/** Matches the public Showcase contract returned by the backend. */
export type PublicShowcaseCategory = 'work' | 'cosmetics' | 'dyes' | 'varnishes'

export type PublicShowcaseItem = {
  id: string
  category: PublicShowcaseCategory
  title: string
  description: string | null
  price_cents: number | null
  image_url: string
}

export type PublicShowcaseResponse = {
  salon_id: string
  items: PublicShowcaseItem[]
}
