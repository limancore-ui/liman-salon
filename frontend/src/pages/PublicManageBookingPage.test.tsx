/**
 * @vitest-environment jsdom
 */
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { PublicManageBookingPage } from './PublicManageBookingPage'
import {
  cancelPublicBookingBySlug,
  getPublicBookingManageBySlug,
  getPublicBookingReviewBySlug,
  getPublicSalon,
  getPublicServiceAvailability,
  getPublicServiceStaff,
  reschedulePublicBookingBySlug,
} from '../api/publicSalon'
import { ApiError } from '../api/errors'
import type { PublicBookingManageResponse } from '../api/publicSalon'
import {
  manageStorageKey,
  persistManageSnapshot,
} from '../utils/manageBookingStorage'
import type { ManageBookingSnapshot } from '../types/publicBooking'
import type { ServiceAvailabilityResponse } from '../types/publicCatalog'

vi.mock('../api/publicSalon', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/publicSalon')>()
  return {
    ...actual,
    getPublicSalon: vi.fn(),
    getPublicBookingManageBySlug: vi.fn(),
    getPublicBookingReviewBySlug: vi.fn(),
    cancelPublicBookingBySlug: vi.fn(),
    reschedulePublicBookingBySlug: vi.fn(),
    getPublicServiceStaff: vi.fn(),
    getPublicServiceAvailability: vi.fn(),
  }
})

vi.mock('../components/SalonHeader', () => ({
  SalonHeader: ({ name }: { name: string }) => <div>{name}</div>,
}))

const mockedGetSalon = vi.mocked(getPublicSalon)
const mockedGetManage = vi.mocked(getPublicBookingManageBySlug)
const mockedGetReview = vi.mocked(getPublicBookingReviewBySlug)
const mockedCancel = vi.mocked(cancelPublicBookingBySlug)
const mockedReschedule = vi.mocked(reschedulePublicBookingBySlug)
const mockedGetStaff = vi.mocked(getPublicServiceStaff)
const mockedGetAvailability = vi.mocked(getPublicServiceAvailability)

const reactActEnv = globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT?: boolean
}
reactActEnv.IS_REACT_ACT_ENVIRONMENT = true

const SLUG = 'demo-salon'
const BOOKING_ID = 'booking-42'
const TOKEN = 'manage-secret'

function manageApi(
  overrides: Partial<PublicBookingManageResponse> = {},
): PublicBookingManageResponse {
  return {
    booking_id: BOOKING_ID,
    status: 'confirmed',
    service_id: 'svc-1',
    service_name: 'Стрижка',
    staff_id: 'staff-1',
    staff_display_name: 'Мария',
    service_start: '2026-08-01T09:00:00.000Z',
    service_end: '2026-08-01T10:00:00.000Z',
    hold_expires_at: null,
    can_cancel: true,
    can_reschedule: true,
    timezone: 'Europe/Moscow',
    ...overrides,
  }
}

function fullSnapshot(
  overrides: Partial<ManageBookingSnapshot> = {},
): ManageBookingSnapshot {
  return {
    token: TOKEN,
    booking_id: BOOKING_ID,
    slug: SLUG,
    salon_id: 'salon-1',
    service_id: 'svc-1',
    staff_id: 'staff-1',
    service_name: 'Стрижка (кэш)',
    staff_display_name: 'Мария',
    service_start: '2026-08-01T09:00:00.000Z',
    service_end: '2026-08-01T10:00:00.000Z',
    hold_expires_at: '',
    status: 'confirmed',
    ...overrides,
  }
}

function flushPromises() {
  return new Promise<void>((resolve) => {
    setTimeout(resolve, 0)
  })
}

async function settle() {
  await act(async () => {
    await flushPromises()
    await flushPromises()
  })
}

function renderManagePage(initialEntry: string) {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root: Root = createRoot(container)

  act(() => {
    root.render(
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route
            path="/s/:slug/bookings/:bookingId/manage"
            element={<PublicManageBookingPage />}
          />
        </Routes>
      </MemoryRouter>,
    )
  })

  return {
    container,
    cleanup() {
      act(() => root.unmount())
      container.remove()
    },
  }
}

describe('PublicManageBookingPage manage GET', () => {
  beforeEach(() => {
    mockedGetSalon.mockResolvedValue({
      name: 'Demo Salon',
      logo_url: null,
      timezone: 'UTC',
    } as Awaited<ReturnType<typeof getPublicSalon>>)
    mockedGetReview.mockRejectedValue(new ApiError(404, 'not found'))
  })

  afterEach(() => {
    sessionStorage.clear()
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('loads booking from deep link without sessionStorage and sends token to API', async () => {
    mockedGetManage.mockResolvedValue(manageApi())
    const path = `/s/${SLUG}/bookings/${BOOKING_ID}/manage?token=${TOKEN}`
    const { container, cleanup } = renderManagePage(path)

    await settle()

    expect(mockedGetManage).toHaveBeenCalledWith(
      SLUG,
      BOOKING_ID,
      TOKEN,
      expect.any(AbortSignal),
    )
    expect(container.textContent).toContain('Стрижка')
    expect(container.textContent).toContain('Мария')
    expect(
      sessionStorage.getItem(manageStorageKey(SLUG, BOOKING_ID)),
    ).toContain('"service_name":"Стрижка"')
    cleanup()
  })

  it('shows loading state while manage GET is in flight', async () => {
    let resolveManage!: (value: PublicBookingManageResponse) => void
    mockedGetManage.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveManage = resolve
        }),
    )
    const path = `/s/${SLUG}/bookings/${BOOKING_ID}/manage?token=${TOKEN}`
    const { container, cleanup } = renderManagePage(path)

    await settle()
    expect(container.textContent).toContain('Загрузка записи')

    await act(async () => {
      resolveManage(manageApi())
      await settle()
    })

    expect(container.textContent).not.toContain('Загрузка записи…')
    cleanup()
  })

  it('shows fatal error on manage 404', async () => {
    mockedGetManage.mockRejectedValue(new ApiError(404, 'missing'))
    const path = `/s/${SLUG}/bookings/${BOOKING_ID}/manage?token=${TOKEN}`
    const { container, cleanup } = renderManagePage(path)

    await settle()

    expect(container.textContent).toContain('Ссылка недействительна')
    expect(container.textContent).toContain(
      'Запись не найдена или ссылка недействительна.',
    )
    cleanup()
  })

  it('keeps snapshot data and shows network notice on transient manage error', async () => {
    persistManageSnapshot(fullSnapshot())
    mockedGetManage.mockRejectedValue(new ApiError(0, 'network error'))
    const path = `/s/${SLUG}/bookings/${BOOKING_ID}/manage`
    const { container, cleanup } = renderManagePage(path)

    await settle()

    expect(container.textContent).toContain('Стрижка (кэш)')
    expect(container.textContent).toContain(
      'Нет связи с сервером. Проверьте интернет и попробуйте снова.',
    )
    expect(container.textContent).not.toContain(
      'Откройте страницу из подтверждения записи',
    )
    cleanup()
  })

  it('uses can_cancel and can_reschedule from backend for action buttons', async () => {
    mockedGetManage.mockResolvedValue(
      manageApi({ can_cancel: false, can_reschedule: false }),
    )
    const path = `/s/${SLUG}/bookings/${BOOKING_ID}/manage?token=${TOKEN}`
    const { container, cleanup } = renderManagePage(path)

    await settle()

    const rescheduleBtn = Array.from(container.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Перенести запись'),
    )
    const cancelBtn = Array.from(container.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Отменить запись'),
    )
    expect(rescheduleBtn?.disabled).toBe(true)
    expect(cancelBtn?.disabled).toBe(true)
    cleanup()
  })

  it('aborts in-flight manage request on unmount', async () => {
    let capturedSignal: AbortSignal | undefined
    mockedGetManage.mockImplementation((_s, _b, _t, signal) => {
      capturedSignal = signal
      return new Promise(() => {
        /* never resolves */
      })
    })
    const path = `/s/${SLUG}/bookings/${BOOKING_ID}/manage?token=${TOKEN}`
    const { cleanup } = renderManagePage(path)

    await settle()
    expect(capturedSignal?.aborted).toBe(false)

    cleanup()
    expect(capturedSignal?.aborted).toBe(true)
  })

  it('still works with same-device session snapshot after refresh merge', async () => {
    persistManageSnapshot(
      fullSnapshot({
        service_name: 'Кэш до API',
        can_reschedule: undefined,
      }),
    )
    mockedGetManage.mockResolvedValue(
      manageApi({ service_name: 'Актуальная услуга' }),
    )
    const path = `/s/${SLUG}/bookings/${BOOKING_ID}/manage`
    const { container, cleanup } = renderManagePage(path)

    await settle()

    expect(mockedGetManage).toHaveBeenCalled()
    expect(container.textContent).toContain('Актуальная услуга')
    const stored = sessionStorage.getItem(manageStorageKey(SLUG, BOOKING_ID))
    expect(stored).toContain('"service_name":"Актуальная услуга"')
    cleanup()
  })

  it('does not enable actions from stale permissions when manage GET fails', async () => {
    persistManageSnapshot(
      fullSnapshot({ can_cancel: true, can_reschedule: true }),
    )
    mockedGetManage.mockRejectedValue(new ApiError(0, 'network error'))
    const path = `/s/${SLUG}/bookings/${BOOKING_ID}/manage`
    const { container, cleanup } = renderManagePage(path)

    await settle()

    const rescheduleBtn = Array.from(container.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Перенести запись'),
    )
    const cancelBtn = Array.from(container.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Отменить запись'),
    )
    expect(rescheduleBtn?.disabled).toBe(true)
    expect(cancelBtn?.disabled).toBe(true)
    cleanup()
  })
})

describe('PublicManageBookingPage cancel/reschedule consistency', () => {
  beforeEach(() => {
    mockedGetSalon.mockResolvedValue({
      name: 'Demo Salon',
      logo_url: null,
      timezone: 'UTC',
    } as Awaited<ReturnType<typeof getPublicSalon>>)
    mockedGetReview.mockRejectedValue(new ApiError(404, 'not found'))
    mockedGetManage.mockResolvedValue(manageApi())
  })

  afterEach(() => {
    sessionStorage.clear()
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('shows cancelled state after cancel, persist, and remount', async () => {
    const path = `/s/${SLUG}/bookings/${BOOKING_ID}/manage?token=${TOKEN}`
    const first = renderManagePage(path)
    await settle()

    mockedCancel.mockResolvedValue({
      booking_id: BOOKING_ID,
      status: 'cancelled',
      cancelled_at: '2026-08-02T08:00:00.000Z',
    })

    const cancelBtn = Array.from(first.container.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Отменить запись'),
    )
    expect(cancelBtn).toBeTruthy()
    await act(async () => {
      cancelBtn!.click()
      await settle()
    })

    const confirmBtn = Array.from(first.container.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Подтвердить отмену'),
    )
    await act(async () => {
      confirmBtn!.click()
      await settle()
    })

    expect(first.container.textContent).toContain('Запись отменена')
    expect(
      sessionStorage.getItem(manageStorageKey(SLUG, BOOKING_ID)),
    ).toContain(`"token":"${TOKEN}"`)
    first.cleanup()

    mockedGetManage.mockResolvedValue(
      manageApi({
        status: 'cancelled',
        can_cancel: false,
        can_reschedule: false,
      }),
    )

    const second = renderManagePage(
      `/s/${SLUG}/bookings/${BOOKING_ID}/manage`,
    )
    await settle()

    expect(mockedGetManage).toHaveBeenCalledWith(
      SLUG,
      BOOKING_ID,
      TOKEN,
      expect.any(AbortSignal),
    )
    expect(second.container.textContent).toContain('Запись отменена')
    expect(second.container.textContent).not.toContain('Ссылка недействительна')
    expect(
      Array.from(second.container.querySelectorAll('button')).some((b) =>
        b.textContent?.includes('Отменить запись'),
      ),
    ).toBe(false)
    expect(
      Array.from(second.container.querySelectorAll('button')).some((b) =>
        b.textContent?.includes('Перенести запись'),
      ),
    ).toBe(false)
    second.cleanup()
  })

  it('reload after cancel with deep-link token confirms via GET and hides actions', async () => {
    const path = `/s/${SLUG}/bookings/${BOOKING_ID}/manage?token=${TOKEN}`
    const first = renderManagePage(path)
    await settle()

    mockedCancel.mockResolvedValue({
      booking_id: BOOKING_ID,
      status: 'cancelled',
      cancelled_at: '2026-08-02T08:00:00.000Z',
    })

    const cancelBtn = Array.from(first.container.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Отменить запись'),
    )
    await act(async () => {
      cancelBtn!.click()
      await settle()
    })
    const confirmBtn = Array.from(first.container.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Подтвердить отмену'),
    )
    await act(async () => {
      confirmBtn!.click()
      await settle()
    })
    first.cleanup()

    mockedGetManage.mockResolvedValue(
      manageApi({
        status: 'cancelled',
        can_cancel: false,
        can_reschedule: false,
      }),
    )

    const second = renderManagePage(path)
    await settle()

    expect(mockedGetManage).toHaveBeenCalled()
    expect(second.container.textContent).toContain('Запись отменена')
    expect(
      Array.from(second.container.querySelectorAll('button')).some((b) =>
        b.textContent?.includes('Отменить запись'),
      ),
    ).toBe(false)
    second.cleanup()
  })

  it('refreshes permissions from manage GET after successful reschedule', async () => {
    const slotDate = '2026-08-03'
    const slotStart = `${slotDate}T14:00:00.000Z`
    const slotEnd = `${slotDate}T15:00:00.000Z`
    vi.setSystemTime(new Date(`${slotDate}T10:00:00.000Z`))

    persistManageSnapshot(fullSnapshot())
    mockedGetManage
      .mockResolvedValueOnce(manageApi({ can_reschedule: true, can_cancel: true }))
      .mockResolvedValueOnce(
        manageApi({
          can_reschedule: false,
          can_cancel: true,
          service_start: slotStart,
          service_end: slotEnd,
          staff_id: 'staff-2',
          staff_display_name: 'Иван',
        }),
      )

    mockedGetStaff.mockResolvedValue({
      staff: [{ id: 'staff-2', display_name: 'Иван' }],
    } as Awaited<ReturnType<typeof getPublicServiceStaff>>)

    const availability: ServiceAvailabilityResponse = {
      service_id: 'svc-1',
      staff: [
        {
          staff_id: 'staff-2',
          slots: [{ service_start: slotStart, service_end: slotEnd }],
        },
      ],
    }
    mockedGetAvailability.mockResolvedValue(availability)

    mockedReschedule.mockResolvedValue({
      booking_id: BOOKING_ID,
      status: 'confirmed',
      staff_id: 'staff-2',
      service_start: slotStart,
      service_end: slotEnd,
    })

    const path = `/s/${SLUG}/bookings/${BOOKING_ID}/manage`
    const { container, cleanup } = renderManagePage(path)
    await settle()

    const clickButton = async (label: string) => {
      const btn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes(label),
      )
      expect(btn).toBeTruthy()
      await act(async () => {
        btn!.click()
        await settle()
      })
    }

    await clickButton('Перенести запись')
    await clickButton('Любой мастер')

    const dateChip = container.querySelector('button.date-chip') as HTMLButtonElement
    expect(dateChip).toBeTruthy()
    await act(async () => {
      dateChip.click()
      await settle()
    })

    const timeSlot = container.querySelector(
      '.time-list__item button',
    ) as HTMLButtonElement
    expect(timeSlot).toBeTruthy()
    await act(async () => {
      timeSlot.click()
      await settle()
    })

    await clickButton('Подтвердить перенос')

    expect(mockedGetManage).toHaveBeenCalledTimes(2)
    expect(mockedReschedule).toHaveBeenCalled()
    const rescheduleBtn = Array.from(container.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Перенести запись'),
    )
    expect(rescheduleBtn?.disabled).toBe(true)
    expect(container.textContent).toContain('Иван')
    cleanup()
    vi.useRealTimers()
  })
})
