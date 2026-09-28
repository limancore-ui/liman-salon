import {
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
} from 'react'
import { AdminLayout } from '../components/AdminLayout'
import { AdminMediaPreview } from '../components/AdminMediaPreview'
import { useAuth } from '../auth/AuthContext'
import {
  deleteAdminMedia,
  detachAdminMediaAttachment,
  uploadAdminMedia,
} from '../api/media'
import { ApiError } from '../api/errors'
import { isUnauthorizedError } from '../api/auth'
import { AdminEntityMediaAttach } from '../components/AdminEntityMediaAttach'
import { useSalonMediaAttachmentIndex } from '../hooks/useSalonMediaAttachmentIndex'
import { groupAttachmentsByMediaId } from '../utils/entityMediaAttachment'

const UPLOAD_ACCEPT = 'image/jpeg,image/png,image/webp'

function canManageMedia(role: string | undefined): boolean {
  return role === 'owner' || role === 'admin'
}

function formatByteSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function AdminMediaPage() {
  const { session, clearAuthAndRedirect } = useAuth()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const mediaIndex = useSalonMediaAttachmentIndex(
    session?.token,
    session?.salon.salon_id,
    clearAuthAndRedirect,
  )
  const attachmentsByMediaId = useMemo(
    () => groupAttachmentsByMediaId(mediaIndex.indexItems),
    [mediaIndex.indexItems],
  )
  const [uploading, setUploading] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [detachingKey, setDetachingKey] = useState<string | null>(null)

  const canWrite = canManageMedia(session?.salon.role)
  const { assets, loading, error, reload } = mediaIndex

  const handleUploadClick = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file || !session || !canWrite) {
      return
    }
    setUploading(true)
    setActionError(null)
    try {
      await uploadAdminMedia(session.token, session.salon.salon_id, file)
      await reload()
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      setActionError(
        err instanceof ApiError ? err.message : 'Upload failed.',
      )
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async (mediaId: string) => {
    if (!session || !canWrite) {
      return
    }
    if (!window.confirm('Delete this media asset?')) {
      return
    }
    setDeletingId(mediaId)
    setActionError(null)
    try {
      await deleteAdminMedia(session.token, session.salon.salon_id, mediaId)
      await reload()
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      setActionError(
        err instanceof ApiError ? err.message : 'Delete failed.',
      )
    } finally {
      setDeletingId(null)
    }
  }

  const handleDetach = async (mediaId: string, attachmentId: string) => {
    if (!session || !canWrite) {
      return
    }
    const key = `${mediaId}:${attachmentId}`
    setDetachingKey(key)
    setActionError(null)
    try {
      await detachAdminMediaAttachment(
        session.token,
        session.salon.salon_id,
        mediaId,
        attachmentId,
      )
      await reload()
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      setActionError(
        err instanceof ApiError ? err.message : 'Detach failed.',
      )
    } finally {
      setDetachingKey(null)
    }
  }

  const logoAttachment =
    session != null
      ? mediaIndex.getAttachment('salon', session.salon.salon_id, 'logo')
      : null

  return (
    <AdminLayout>
      <section className="admin-media">
        <header className="admin-media__header">
          <h1 className="admin-media__title">Media</h1>
          <p className="admin-media__lead">
            Upload images for your salon library. Attachments show where each file is used.
          </p>
        </header>

        {session ? (
          <div className="admin-media__salon-logo">
            <AdminEntityMediaAttach
              token={session.token}
              salonId={session.salon.salon_id}
              canWrite={canWrite}
              entityType="salon"
              entityId={session.salon.salon_id}
              purpose="logo"
              label="Salon logo"
              assets={assets}
              attachment={logoAttachment}
              attachmentLoading={loading}
              onUpdated={reload}
              onUnauthorized={clearAuthAndRedirect}
            />
          </div>
        ) : null}

        {canWrite ? (
          <div className="admin-media__toolbar">
            <input
              ref={fileInputRef}
              type="file"
              accept={UPLOAD_ACCEPT}
              className="admin-media__file-input"
              onChange={(event) => void handleFileChange(event)}
            />
            <button
              type="button"
              className="btn btn--primary"
              disabled={uploading}
              onClick={handleUploadClick}
            >
              {uploading ? 'Uploading…' : 'Upload image'}
            </button>
            <span className="admin-media__hint">JPEG, PNG, or WebP</span>
          </div>
        ) : (
          <p className="admin-media__read-only">Read-only for your role.</p>
        )}

        {actionError ? (
          <p className="admin-media__state admin-media__state--error" role="alert">
            {actionError}
          </p>
        ) : null}

        {loading ? (
          <p className="admin-media__state" role="status">
            Loading media…
          </p>
        ) : null}

        {!loading && error ? (
          <p className="admin-media__state admin-media__state--error" role="alert">
            {error}
          </p>
        ) : null}

        {!loading && !error && assets.length === 0 ? (
          <p className="admin-media__state">No media uploaded yet.</p>
        ) : null}

        {!loading && !error && assets.length > 0 && session ? (
          <ul className="admin-media__list">
            {assets.map((asset) => {
              const attachments = attachmentsByMediaId.get(asset.id) ?? []
              return (
                <li key={asset.id} className="admin-media__item">
                  <AdminMediaPreview
                    token={session.token}
                    salonId={session.salon.salon_id}
                    mediaId={asset.id}
                    alt={asset.original_filename}
                    className="admin-media__thumb"
                  />
                  <div className="admin-media__meta">
                    <p className="admin-media__filename">{asset.original_filename}</p>
                    <p className="admin-media__type">{asset.content_type}</p>
                    <p className="admin-media__size">{formatByteSize(asset.byte_size)}</p>
                    {attachments.length === 0 ? (
                      <p className="admin-media__attachments">Not attached to any entity.</p>
                    ) : (
                      <ul className="admin-media__attachments-list">
                        {attachments.map((attachment) => (
                          <li
                            key={attachment.attachment_id}
                            className="admin-media__attachment"
                          >
                            <span>
                              {attachment.entity_type} / {attachment.purpose} →{' '}
                              {attachment.entity_id}
                            </span>
                            {canWrite ? (
                              <button
                                type="button"
                                className="btn btn--secondary btn--compact"
                                disabled={
                                  detachingKey ===
                                  `${asset.id}:${attachment.attachment_id}`
                                }
                                onClick={() =>
                                  void handleDetach(asset.id, attachment.attachment_id)
                                }
                              >
                                Detach
                              </button>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  {canWrite ? (
                    <button
                      type="button"
                      className="btn btn--secondary btn--compact admin-media__delete"
                      disabled={deletingId === asset.id}
                      onClick={() => void handleDelete(asset.id)}
                    >
                      {deletingId === asset.id ? 'Deleting…' : 'Delete'}
                    </button>
                  ) : null}
                </li>
              )
            })}
          </ul>
        ) : null}
      </section>
    </AdminLayout>
  )
}
