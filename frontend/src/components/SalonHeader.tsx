type SalonHeaderProps = {
  name: string
}

export function SalonHeader({ name }: SalonHeaderProps) {
  return (
    <header className="salon-header">
      <h1 className="salon-header__title">{name}</h1>
      <p className="salon-header__subtitle">Services</p>
    </header>
  )
}
