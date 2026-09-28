import { useEffect, useState } from 'react'
import { fetchAdminMediaContentBlob } from '../api/media'

type AdminMediaPreviewProps = {
  token: string
  salonId: string
  mediaId: string
  alt: string
  className?: string
}

export function AdminMediaPreview({
  token,
  salonId,
  mediaId,
  alt,
  className,
}: AdminMediaPreviewProps) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    let url: string | null = null
    setFailed(false)
    setObjectUrl(null)

    fetchAdminMediaContentBlob(token, salonId, mediaId)
      .then((blob) => {
        if (cancelled) {
          return
        }
        url = URL.createObjectURL(blob)
        setObjectUrl(url)
      })
      .catch(() => {
        if (!cancelled) {
          setFailed(true)
        }
      })

    return () => {
      cancelled = true
      if (url) {
        URL.revokeObjectURL(url)
      }
    }
  }, [token, salonId, mediaId])

  if (failed || !objectUrl) {
    return (
      <div className={`admin-media-preview admin-media-preview--empty${className ? ` ${className}` : ''}`}>
        <span className="admin-media-preview__placeholder">No preview</span>
      </div>
    )
  }

  return (
    <img
      src={objectUrl}
      alt={alt}
      className={`admin-media-preview${className ? ` ${className}` : ''}`}
      onError={() => setFailed(true)}
    />
  )
}
