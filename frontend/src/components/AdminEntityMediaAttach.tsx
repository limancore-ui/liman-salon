import { useState } from 'react'
import { AdminMediaPreview } from './AdminMediaPreview'
import {
  attachAdminMedia,
  detachAdminMediaAttachment,
} from '../api/media'
import { ApiError } from '../api/errors'
import { isUnauthorizedError } from '../api/auth'
import type { EntityAttachmentRef } from '../hooks/useSalonMediaAttachmentIndex'
import type {
  MediaAssetResponse,
  MediaEntityType,
  MediaPurpose,
} from '../types/media'

type AdminEntityMediaAttachProps = {
  token: string
  salonId: string
  canWrite: boolean
  entityType: MediaEntityType
  entityId: string
  purpose: MediaPurpose
  label: string
  assets: MediaAssetResponse[]
  attachment: EntityAttachmentRef | null
  attachmentLoading?: boolean
  onUpdated: () => void
  onUnauthorized: () => void
  compact?: boolean
}

export function AdminEntityMediaAttach({
  token,
  salonId,
  canWrite,
  entityType,
  entityId,
  purpose,
  label,
  assets,
  attachment,
  attachmentLoading = false,
  onUpdated,
  onUnauthorized,
  compact = false,
}: AdminEntityMediaAttachProps) {
  const [selectedMediaId, setSelectedMediaId] = useState('')
  const [busy, setBusy] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  const handleAttach = async () => {
    if (!canWrite || !selectedMediaId) {
      return
    }
    setBusy(true)
    setLocalError(null)
    try {
      await attachAdminMedia(token, salonId, selectedMediaId, {
        entity_type: entityType,
        entity_id: entityId,
        purpose,
        sort_order: 0,
      })
      setSelectedMediaId('')
      await onUpdated()
    } catch (err) {
      if (isUnauthorizedError(err)) {
        onUnauthorized()
        return
      }
      setLocalError(
        err instanceof ApiError ? err.message : 'Could not attach image.',
      )
    } finally {
      setBusy(false)
    }
  }

  const handleDetach = async () => {
    if (!canWrite || !attachment) {
      return
    }
    setBusy(true)
    setLocalError(null)
    try {
      await detachAdminMediaAttachment(
        token,
        salonId,
        attachment.mediaId,
        attachment.attachmentId,
      )
      setSelectedMediaId('')
      await onUpdated()
    } catch (err) {
      if (isUnauthorizedError(err)) {
        onUnauthorized()
        return
      }
      setLocalError(
        err instanceof ApiError ? err.message : 'Could not detach image.',
      )
    } finally {
      setBusy(false)
    }
  }

  const rootClass = compact
    ? 'admin-entity-media-attach admin-entity-media-attach--compact'
    : 'admin-entity-media-attach'

  return (
    <div className={rootClass}>
      {!compact ? <p className="admin-entity-media-attach__label">{label}</p> : null}
      {attachmentLoading ? (
        <p className="admin-entity-media-attach__hint" role="status">
          Loading…
        </p>
      ) : null}
      {!attachmentLoading && attachment ? (
        <div className="admin-entity-media-attach__current">
          <AdminMediaPreview
            token={token}
            salonId={salonId}
            mediaId={attachment.mediaId}
            alt={attachment.filename}
            className="admin-entity-media-attach__thumb"
          />
          {!compact ? (
            <p className="admin-entity-media-attach__filename">{attachment.filename}</p>
          ) : null}
        </div>
      ) : null}
      {!attachmentLoading && !attachment ? (
        <p className="admin-entity-media-attach__hint">No image attached.</p>
      ) : null}
      {canWrite ? (
        <div className="admin-entity-media-attach__actions">
          {compact ? (
            <span className="admin-entity-media-attach__compact-label">{label}</span>
          ) : null}
          <select
            className="admin-entity-media-attach__select"
            value={selectedMediaId}
            disabled={busy || assets.length === 0}
            aria-label={`${label} — choose from library`}
            onChange={(event) => setSelectedMediaId(event.target.value)}
          >
            <option value="">
              {assets.length === 0 ? 'No media in library' : 'Choose from library…'}
            </option>
            {assets.map((asset) => (
              <option key={asset.id} value={asset.id}>
                {asset.original_filename}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="btn btn--primary btn--compact"
            disabled={busy || !selectedMediaId}
            onClick={() => void handleAttach()}
          >
            {busy ? 'Saving…' : attachment ? 'Replace' : 'Attach'}
          </button>
          {attachment ? (
            <button
              type="button"
              className="btn btn--secondary btn--compact"
              disabled={busy}
              onClick={() => void handleDetach()}
            >
              Detach
            </button>
          ) : null}
        </div>
      ) : null}
      {localError ? (
        <p className="admin-entity-media-attach__error" role="alert">
          {localError}
        </p>
      ) : null}
    </div>
  )
}
