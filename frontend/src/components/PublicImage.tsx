import { useState } from 'react'

type PublicImageProps = {
  src: string | null | undefined
  alt: string
  className?: string
}

export function PublicImage({ src, alt, className }: PublicImageProps) {
  const [hidden, setHidden] = useState(!src)

  if (!src || hidden) {
    return null
  }

  return (
    <img
      src={src}
      alt={alt}
      className={className}
      onError={() => setHidden(true)}
    />
  )
}
