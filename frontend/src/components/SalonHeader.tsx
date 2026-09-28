import { PublicImage } from './PublicImage'

type SalonHeaderProps = {
  name: string
  logoUrl?: string | null
}

export function SalonHeader({ name, logoUrl }: SalonHeaderProps) {
  return (
    <header className="salon-header">
      <PublicImage
        src={logoUrl}
        alt={`${name} logo`}
        className="salon-header__logo"
      />
      <h1 className="salon-header__title">{name}</h1>
      <p className="salon-header__subtitle">Services</p>
    </header>
  )
}
