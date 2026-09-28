import { useCallback, useEffect, useState } from 'react'
import {
  fetchAdminMediaAttachmentIndex,
  fetchAdminMediaList,
} from '../api/media'
import { ApiError } from '../api/errors'
import { isUnauthorizedError } from '../api/auth'
import type {
  MediaAssetResponse,
  MediaAttachmentIndexItem,
  MediaEntityType,
  MediaPurpose,
} from '../types/media'

export type EntityAttachmentRef = {
  mediaId: string
  attachmentId: string
  filename: string
}

function attachmentKey(
  entityType: string,
  entityId: string,
  purpose: string,
): string {
  return `${entityType}:${entityId}:${purpose}`
}

export function useSalonMediaAttachmentIndex(
  token: string | undefined,
  salonId: string | undefined,
  clearAuthAndRedirect: () => void,
) {
  const [assets, setAssets] = useState<MediaAssetResponse[]>([])
  const [indexItems, setIndexItems] = useState<MediaAttachmentIndexItem[]>([])
  const [index, setIndex] = useState<Map<string, EntityAttachmentRef>>(new Map())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    if (!token || !salonId) {
      return
    }
    setLoading(true)
    setError(null)
    try {
      const [list, attachmentRows] = await Promise.all([
        fetchAdminMediaList(token, salonId),
        fetchAdminMediaAttachmentIndex(token, salonId),
      ])
      setAssets(list)
      setIndexItems(attachmentRows)
      const map = new Map<string, EntityAttachmentRef>()
      for (const row of attachmentRows) {
        map.set(
          attachmentKey(row.entity_type, row.entity_id, row.purpose),
          {
            mediaId: row.media_id,
            attachmentId: row.attachment_id,
            filename: row.filename,
          },
        )
      }
      setIndex(map)
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      setError(
        err instanceof ApiError
          ? err.message
          : 'Could not load media attachments.',
      )
      setAssets([])
      setIndexItems([])
      setIndex(new Map())
    } finally {
      setLoading(false)
    }
  }, [token, salonId, clearAuthAndRedirect])

  useEffect(() => {
    void reload()
  }, [reload])

  const getAttachment = useCallback(
    (
      entityType: MediaEntityType,
      entityId: string,
      purpose: MediaPurpose,
    ): EntityAttachmentRef | null => {
      return index.get(attachmentKey(entityType, entityId, purpose)) ?? null
    },
    [index],
  )

  return { assets, indexItems, getAttachment, loading, error, reload }
}
