/**
 * @vitest-environment jsdom
 */
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { BookingConfirmation } from './BookingConfirmation'
import * as copyModule from '../utils/copyTextToClipboard'
import { persistManageSnapshot } from '../utils/manageBookingStorage'

const reactActEnv = globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT?: boolean
}
reactActEnv.IS_REACT_ACT_ENVIRONMENT = true

const booking = {
  salon_id: 'salon-1',
  customer_id: 'cust-1',
  booking_id: 'booking-99',
  service_start: '2026-07-10T10:00:00.000Z',
  service_end: '2026-07-10T11:00:00.000Z',
  hold_expires_at: '2026-07-10T12:00:00.000Z',
  manage_token: 'manage-token-value',
}

function LocationProbe() {
  const location = useLocation()
  return (
    <div
      data-testid="location"
      data-pathname={location.pathname}
      data-search={location.search}
    />
  )
}

function renderConfirmation(onDone = vi.fn()) {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root: Root = createRoot(container)

  act(() => {
    root.render(
      <MemoryRouter initialEntries={['/s/demo-salon']}>
        <Routes>
          <Route
            path="/s/:slug"
            element={
              <>
                <BookingConfirmation
                  booking={booking}
                  slug="demo-salon"
                  timeZone="UTC"
                  onDone={onDone}
                />
                <LocationProbe />
              </>
            }
          />
          <Route
            path="/s/:slug/bookings/:bookingId/manage"
            element={<LocationProbe />}
          />
        </Routes>
      </MemoryRouter>,
    )
  })

  return {
    container,
    root,
    cleanup() {
      act(() => root.unmount())
      container.remove()
    },
  }
}

describe('BookingConfirmation', () => {
  afterEach(() => {
    sessionStorage.clear()
    vi.restoreAllMocks()
    document.body.innerHTML = ''
  })

  it('shows manage deep link with token in readonly field', () => {
    const { container, cleanup } = renderConfirmation()
    const input = container.querySelector(
      '#booking-manage-link',
    ) as HTMLInputElement
    expect(input).not.toBeNull()
    expect(input.value).toBe(
      `${window.location.origin}/s/demo-salon/bookings/booking-99/manage?token=manage-token-value`,
    )
    expect(container.textContent).toContain('Запись успешно оформлена!')
    expect(container.textContent).toContain(
      'Ваше время зарезервировано. Ждём вас!',
    )
    expect(container.textContent).toContain(
      'Нужно перенести или отменить запись?',
    )
    expect(container.textContent).toContain('персональную ссылку')
    expect(container.textContent).not.toContain('ожидает подтверждения')
    expect(container.textContent).not.toContain('Удержание до')
    expect(container.textContent).not.toContain('освобождён')
    expect(container.textContent).not.toContain('Malina')
    cleanup()
  })

  it('renders salon brand for the correct salon when provided', () => {
    const container = document.createElement('div')
    document.body.appendChild(container)
    const root: Root = createRoot(container)
    act(() => {
      root.render(
        <MemoryRouter initialEntries={['/s/sever']}>
          <BookingConfirmation
            booking={booking}
            slug="sever"
            timeZone="UTC"
            salonName="Студия Север"
            logoUrl="/api/v1/public/salons/sever/media/logo-9/content"
            onDone={vi.fn()}
          />
        </MemoryRouter>,
      )
    })

    expect(container.textContent).toContain('Студия Север')
    expect(container.textContent).not.toContain('Malina')
    const img = container.querySelector('img.salon-header__logo') as HTMLImageElement
    expect(img?.getAttribute('src')).toContain('/salons/sever/media/logo-9/')
    expect(img?.getAttribute('alt')).toBe('Логотип салона Студия Север')
    act(() => root.unmount())
    container.remove()
  })

  it('copies manage link when copy button clicked', async () => {
    const copySpy = vi
      .spyOn(copyModule, 'copyTextToClipboard')
      .mockResolvedValue(true)
    const { container, cleanup } = renderConfirmation()

    const copyBtn = Array.from(container.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Скопировать ссылку'),
    )
    expect(copyBtn).toBeDefined()
    expect(copyBtn?.className).toContain('btn--secondary')

    await act(async () => {
      copyBtn!.click()
    })

    expect(copySpy).toHaveBeenCalledWith(
      `${window.location.origin}/s/demo-salon/bookings/booking-99/manage?token=manage-token-value`,
    )
    expect(container.textContent).toContain('Ссылка скопирована')
    cleanup()
  })

  it('shows fallback hint when clipboard copy fails without crashing', async () => {
    vi.spyOn(copyModule, 'copyTextToClipboard').mockResolvedValue(false)
    const { container, cleanup } = renderConfirmation()

    const copyBtn = Array.from(container.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Скопировать ссылку'),
    )

    await act(async () => {
      copyBtn!.click()
    })

    expect(container.textContent).toContain('выделите ссылку ниже')
    cleanup()
  })

  it('uses primary style for manage and secondary for copy', () => {
    const { container, cleanup } = renderConfirmation()
    const manageBtn = Array.from(container.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Управлять записью'),
    )
    const copyBtn = Array.from(container.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Скопировать ссылку'),
    )
    expect(manageBtn?.className).toContain('btn--primary')
    expect(copyBtn?.className).toContain('btn--secondary')
    cleanup()
  })
  it('navigates to manage path without token and persists session token', async () => {
    const { container, cleanup } = renderConfirmation()

    const manageBtn = Array.from(container.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Управлять записью'),
    )

    await act(async () => {
      manageBtn!.click()
    })

    const location = document.querySelector('[data-testid="location"]')
    expect(location?.getAttribute('data-pathname')).toBe(
      '/s/demo-salon/bookings/booking-99/manage',
    )
    expect(location?.getAttribute('data-search')).toBe('')
    expect(
      sessionStorage.getItem('liman:public-manage:demo-salon:booking-99'),
    ).toContain('"token":"manage-token-value"')
    cleanup()
  })

  it('preserves service labels from prior snapshot when opening manage', async () => {
    persistManageSnapshot({
      token: 'stale',
      booking_id: booking.booking_id,
      slug: 'demo-salon',
      salon_id: booking.salon_id,
      service_id: 'svc',
      staff_id: 'staff',
      service_name: 'Cut',
      staff_display_name: 'Alex',
      service_start: booking.service_start,
      service_end: booking.service_end,
      hold_expires_at: booking.hold_expires_at,
    })

    const { container, cleanup } = renderConfirmation()
    const manageBtn = Array.from(container.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Управлять записью'),
    )

    await act(async () => {
      manageBtn!.click()
    })

    const stored = sessionStorage.getItem(
      'liman:public-manage:demo-salon:booking-99',
    )
    expect(stored).toContain('"service_name":"Cut"')
    expect(stored).toContain('"token":"manage-token-value"')
    cleanup()
  })
})
