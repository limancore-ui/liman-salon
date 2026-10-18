import { useState } from 'react'
import { t } from '../i18n'
import { salonBrandInitials } from '../utils/salonBrandInitials'

type SalonHeaderProps = {
  name: string
  logoUrl?: string | null
  /** When null, subtitle is omitted. When undefined, default catalog subtitle is used. */
  subtitle?: string | null
}

export function SalonHeader({ name, logoUrl, subtitle }: SalonHeaderProps) {
  const resolvedLogo = logoUrl?.trim() ? logoUrl : null
  const [failedLogoSrc, setFailedLogoSrc] = useState<string | null>(null)
  const showLogo = Boolean(resolvedLogo) && failedLogoSrc !== resolvedLogo
  const initials = salonBrandInitials(name)
  const resolvedSubtitle =
    subtitle === undefined ? t('public.servicesSubtitle') : subtitle
  const logoAlt = t('public.salonLogoAlt', { name })

  return (
    <header className="salon-header">
      <div className="salon-header__brand">
        <div
          className="salon-header__mark"
          role={showLogo ? undefined : 'img'}
          aria-label={showLogo ? undefined : logoAlt}
        >
          {showLogo ? (
            <img
              src={resolvedLogo!}
              alt={logoAlt}
              className="salon-header__logo"
              onError={() => setFailedLogoSrc(resolvedLogo)}
            />
          ) : (
            <span className="salon-header__initials" aria-hidden="true">
              {initials}
            </span>
          )}
        </div>
        <div className="salon-header__text">
          <h1 className="salon-header__title">{name}</h1>
          {resolvedSubtitle ? (
            <p className="salon-header__subtitle">{resolvedSubtitle}</p>
          ) : null}
        </div>
      </div>
    </header>
  )
}
