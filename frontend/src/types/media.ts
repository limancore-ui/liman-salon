/** Matches backend `MediaAttachmentResponse`. */
export type MediaAttachmentResponse = {
  id: string
  entity_type: string
  entity_id: string
  purpose: string
  sort_order: number
  created_at: string
}

/** Matches backend `MediaAssetResponse`. */
export type MediaAssetResponse = {
  id: string
  salon_id: string
  original_filename: string
  content_type: string
  byte_size: number
  checksum_sha256: string | null
  width_px: number | null
  height_px: number | null
  created_by_user_id: string | null
  created_at: string
  updated_at: string
}

/** Matches backend `MediaAssetDetailResponse`. */
export type MediaAssetDetailResponse = MediaAssetResponse & {
  attachments: MediaAttachmentResponse[]
}

export type MediaEntityType = 'salon' | 'service' | 'staff'

export type MediaPurpose = 'logo' | 'cover' | 'avatar' | 'gallery'

export type MediaAttachRequest = {
  entity_type: MediaEntityType
  entity_id: string
  purpose: MediaPurpose
  sort_order?: number
}

export type ListMediaParams = {
  limit?: number
  offset?: number
}

/** Matches backend `MediaAttachmentIndexItemResponse`. */
export type MediaAttachmentIndexItem = {
  media_id: string
  attachment_id: string
  filename: string
  entity_type: string
  entity_id: string
  purpose: string
}
