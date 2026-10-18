/**
 * @vitest-environment jsdom
 */
import { act, type ReactElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, describe, expect, it } from 'vitest'
import { SalonHeader } from './SalonHeader'

const reactActEnv = globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT?: boolean
}
reactActEnv.IS_REACT_ACT_ENVIRONMENT = true

function renderHeader(ui: ReactElement) {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root: Root = createRoot(container)
  act(() => {
    root.render(ui)
  })
  return {
    container,
    cleanup() {
      act(() => root.unmount())
      container.remove()
    },
  }
}

describe('SalonHeader', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('renders Russian services subtitle by default', () => {
    const { container, cleanup } = renderHeader(<SalonHeader name="Demo Salon" />)
    expect(container.textContent).toContain('Demo Salon')
    expect(container.textContent).toContain('Услуги')
    expect(container.textContent).not.toContain('Services')
    cleanup()
  })

  it('shows logo image with Russian alt and salon name', () => {
    const { container, cleanup } = renderHeader(
      <SalonHeader
        name="Студия Север"
        logoUrl="/api/v1/public/salons/sever/media/logo-1/content"
      />,
    )
    const img = container.querySelector('img.salon-header__logo') as HTMLImageElement
    expect(img).toBeTruthy()
    expect(img.getAttribute('src')).toBe(
      '/api/v1/public/salons/sever/media/logo-1/content',
    )
    expect(img.getAttribute('alt')).toBe('Логотип салона Студия Север')
    expect(container.textContent).toContain('Студия Север')
    expect(container.querySelector('.salon-header__initials')).toBeNull()
    cleanup()
  })

  it('shows initials fallback when logo is missing', () => {
    const { container, cleanup } = renderHeader(
      <SalonHeader name="Malina Beauty" logoUrl={null} subtitle={null} />,
    )
    expect(container.querySelector('img.salon-header__logo')).toBeNull()
    expect(container.querySelector('.salon-header__initials')?.textContent).toBe(
      'MB',
    )
    expect(container.textContent).toContain('Malina Beauty')
    expect(container.textContent).not.toContain('Услуги')
    cleanup()
  })

  it('renders distinct brands for different salons', () => {
    const first = renderHeader(
      <SalonHeader
        name="Салон А"
        logoUrl="/api/v1/public/salons/a/media/m1/content"
      />,
    )
    expect(first.container.textContent).toContain('Салон А')
    expect(
      first.container.querySelector('img')?.getAttribute('src'),
    ).toContain('/salons/a/media/')
    first.cleanup()

    const second = renderHeader(
      <SalonHeader
        name="Салон Б"
        logoUrl="/api/v1/public/salons/b/media/m2/content"
      />,
    )
    expect(second.container.textContent).toContain('Салон Б')
    expect(second.container.textContent).not.toContain('Салон А')
    expect(
      second.container.querySelector('img')?.getAttribute('src'),
    ).toContain('/salons/b/media/')
    second.cleanup()
  })

  it('falls back to initials when image fails to load without crashing', () => {
    const { container, cleanup } = renderHeader(
      <SalonHeader name="Весна" logoUrl="/broken-logo.png" />,
    )
    const img = container.querySelector('img.salon-header__logo') as HTMLImageElement
    expect(img).toBeTruthy()

    act(() => {
      img.dispatchEvent(new Event('error'))
    })

    expect(container.querySelector('img.salon-header__logo')).toBeNull()
    expect(container.querySelector('.salon-header__initials')?.textContent).toBe(
      'В',
    )
    expect(container.textContent).toContain('Весна')
    cleanup()
  })

  it('supports custom manage subtitle', () => {
    const { container, cleanup } = renderHeader(
      <SalonHeader name="Demo" subtitle="Управление записью" />,
    )
    expect(container.textContent).toContain('Управление записью')
    expect(container.textContent).not.toContain('Услуги')
    cleanup()
  })
})
