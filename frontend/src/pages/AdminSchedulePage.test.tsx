/**
 * @vitest-environment jsdom
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createRoot, type Root } from 'react-dom/client'
import { act, type ReactNode } from 'react'
import { AdminSchedulePage } from './AdminSchedulePage'
import {
  createWorkingHours,
  deleteBlockedPeriod,
  deleteWorkingHours,
  fetchBlockedPeriods,
  fetchWorkingHours,
  previewScheduleImpact,
  updateWorkingHours,
} from '../api/schedule'
import { fetchAdminStaff } from '../api/staff'
import { ApiError } from '../api/errors'
import { useAuth } from '../auth/AuthContext'
import { makeScheduleImpactPreviewResponse } from '../components/scheduleImpactPreviewFixtures'
import type { BlockedPeriodItem, WorkingHoursItem } from '../types/schedule'

vi.mock('../api/schedule', () => ({
  previewScheduleImpact: vi.fn(),
  fetchWorkingHours: vi.fn(),
  fetchBlockedPeriods: vi.fn(),
  createWorkingHours: vi.fn(),
  updateWorkingHours: vi.fn(),
  deleteWorkingHours: vi.fn(),
  createBlockedPeriod: vi.fn(),
  updateBlockedPeriod: vi.fn(),
  deleteBlockedPeriod: vi.fn(),
}))

vi.mock('../api/staff', () => ({
  fetchAdminStaff: vi.fn(),
}))

vi.mock('../auth/AuthContext', () => ({
  useAuth: vi.fn(),
}))

vi.mock('../components/AdminLayout', () => ({
  AdminLayout: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}))

const mockedPreview = vi.mocked(previewScheduleImpact)
const mockedFetchWh = vi.mocked(fetchWorkingHours)
const mockedFetchBp = vi.mocked(fetchBlockedPeriods)
const mockedDeleteWh = vi.mocked(deleteWorkingHours)
const mockedFetchStaff = vi.mocked(fetchAdminStaff)
const mockedUseAuth = vi.mocked(useAuth)

const TOKEN = 'tok-1'
const SALON_ID = 'salon-1'

function makeRow(overrides: Partial<WorkingHoursItem> = {}): WorkingHoursItem {
  return {
    id: 'wh-1',
    staff_id: null,
    day_of_week: 0,
    start_time: '09:00:00',
    end_time: '17:00:00',
    effective_from: null,
    effective_to: null,
    created_at: '2026-01-01T00:00:00+00:00',
    updated_at: '2026-01-01T00:00:00+00:00',
    ...overrides,
  }
}

function setAuth(role: string, clearAuthAndRedirect = vi.fn()) {
  mockedUseAuth.mockReturnValue({
    session: { token: TOKEN, salon: { salon_id: SALON_ID, role } },
    clearAuthAndRedirect,
  } as unknown as ReturnType<typeof useAuth>)
  return clearAuthAndRedirect
}

function impactRow() {
  return {
    booking_id: 'b-1',
    status: 'confirmed',
    is_in_progress: false,
    starts_at: '2026-01-02T10:00:00+00:00',
    ends_at: '2026-01-02T11:00:00+00:00',
    staff_id: 's1',
    service_id: 'v1',
    customer_name: 'Alice',
    service_name: 'Cut',
    reasons: ['outside_availability'],
  }
}

function impactfulResponse() {
  return makeScheduleImpactPreviewResponse({
    impacts: [impactRow()],
    counts: { total_impacted: 1, by_reason: {} },
    pagination: { offset: 0, limit: 50, returned: 1, total_impacted: 1, has_more: false },
    commit_policy: { allow_commit_with_impacts: true, requires_acknowledgement: true },
  })
}

function flushPromises() {
  return new Promise<void>((resolve) => {
    setTimeout(resolve, 0)
  })
}

describe('AdminSchedulePage working hours delete preview', () => {
  let container: HTMLDivElement
  let root: Root

  async function settle() {
    await act(async () => {
      await flushPromises()
      await flushPromises()
    })
  }

  async function renderPage() {
    await act(async () => {
      root.render(<AdminSchedulePage />)
      await flushPromises()
      await flushPromises()
    })
  }

  function buttonByText(scope: ParentNode, text: string): HTMLButtonElement | undefined {
    return Array.from(scope.querySelectorAll('button')).find(
      (b) => b.textContent?.trim() === text,
    ) as HTMLButtonElement | undefined
  }

  function previewPanel(): HTMLElement | null {
    return container.querySelector('.schedule-impact-preview')
  }

  async function click(el: HTMLElement | undefined | null) {
    expect(el).toBeTruthy()
    await act(async () => {
      el?.click()
      await flushPromises()
    })
  }

  beforeEach(() => {
    ;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    vi.clearAllMocks()
    mockedPreview.mockReset()
    mockedFetchWh.mockReset()
    mockedFetchBp.mockReset()
    mockedDeleteWh.mockReset()
    mockedFetchStaff.mockReset()
    mockedFetchWh.mockResolvedValue([makeRow()])
    mockedFetchBp.mockResolvedValue([])
    mockedFetchStaff.mockResolvedValue([])
    mockedDeleteWh.mockResolvedValue(undefined)
    mockedPreview.mockResolvedValue(makeScheduleImpactPreviewResponse())
    setAuth('owner')
    vi.spyOn(window, 'confirm').mockImplementation(() => true)
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
    vi.restoreAllMocks()
  })

  it('Delete click opens the preview with a working_hours.delete change and does not call DELETE', async () => {
    await renderPage()
    await click(buttonByText(container, 'Delete'))
    await settle()

    expect(previewPanel()).not.toBeNull()
    expect(mockedPreview).toHaveBeenCalledTimes(1)
    const [token, salonId, request] = mockedPreview.mock.calls[0]
    expect(token).toBe(TOKEN)
    expect(salonId).toBe(SALON_ID)
    expect(request.change).toEqual({
      kind: 'working_hours.delete',
      working_hours_id: 'wh-1',
    })
    expect(mockedDeleteWh).not.toHaveBeenCalled()
    expect(window.confirm).not.toHaveBeenCalled()
  })

  it('shows the preview even with zero impacts and requires explicit confirm to DELETE', async () => {
    await renderPage()
    await click(buttonByText(container, 'Delete'))
    await settle()

    expect(previewPanel()?.textContent).toContain('No bookings would be affected')
    expect(mockedDeleteWh).not.toHaveBeenCalled()

    await click(buttonByText(previewPanel()!, 'Delete working hours'))
    await settle()
    expect(mockedDeleteWh).toHaveBeenCalledTimes(1)
  })

  it('confirm calls deleteWorkingHours with token, salon id and snapshot id only (no fingerprint)', async () => {
    await renderPage()
    await click(buttonByText(container, 'Delete'))
    await settle()
    await click(buttonByText(previewPanel()!, 'Delete working hours'))
    await settle()

    expect(mockedDeleteWh).toHaveBeenCalledTimes(1)
    expect(mockedDeleteWh.mock.calls[0]).toEqual([TOKEN, SALON_ID, 'wh-1'])
    expect(JSON.stringify(mockedDeleteWh.mock.calls[0])).not.toContain('f'.repeat(64))
    // list reloaded after delete, preview closed
    expect(mockedFetchWh.mock.calls.length).toBeGreaterThanOrEqual(2)
    expect(previewPanel()).toBeNull()
  })

  it('Cancel closes the preview and does not call DELETE', async () => {
    await renderPage()
    await click(buttonByText(container, 'Delete'))
    await settle()
    await click(buttonByText(previewPanel()!, 'Cancel'))
    await settle()

    expect(previewPanel()).toBeNull()
    expect(mockedDeleteWh).not.toHaveBeenCalled()
  })

  it('confirm stays disabled until acknowledgement when impacts require it', async () => {
    mockedPreview.mockResolvedValue(impactfulResponse())
    await renderPage()
    await click(buttonByText(container, 'Delete'))
    await settle()

    const confirmBtn = buttonByText(previewPanel()!, 'Delete working hours')
    expect(confirmBtn?.disabled).toBe(true)
    await click(confirmBtn)
    expect(mockedDeleteWh).not.toHaveBeenCalled()

    const checkbox = previewPanel()!.querySelector('input[type="checkbox"]') as HTMLInputElement
    await click(checkbox)
    expect(buttonByText(previewPanel()!, 'Delete working hours')?.disabled).toBe(false)

    await click(buttonByText(previewPanel()!, 'Delete working hours'))
    await settle()
    expect(mockedDeleteWh).toHaveBeenCalledTimes(1)
    expect(mockedDeleteWh.mock.calls[0]).toEqual([TOKEN, SALON_ID, 'wh-1'])
  })

  it('confirm uses the frozen snapshot, not live rows that change while the preview is open', async () => {
    mockedFetchStaff.mockResolvedValue([
      {
        id: 'staff-9',
        display_name: 'Bob',
      } as unknown as Awaited<ReturnType<typeof fetchAdminStaff>>[number],
    ])
    await renderPage()
    await click(buttonByText(container, 'Delete'))
    await settle()
    expect(previewPanel()).not.toBeNull()

    // Live list changes underneath the open preview: scope switch reloads other rows.
    mockedFetchWh.mockResolvedValue([makeRow({ id: 'wh-2', staff_id: 'staff-9' })])
    const scope = container.querySelector('select') as HTMLSelectElement
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(
        HTMLSelectElement.prototype,
        'value',
      )?.set
      setter?.call(scope, 'staff-9')
      scope.dispatchEvent(new Event('change', { bubbles: true }))
      await flushPromises()
      await flushPromises()
    })

    expect(container.textContent).not.toContain('No working hours defined')
    await click(buttonByText(previewPanel()!, 'Delete working hours'))
    await settle()

    expect(mockedDeleteWh).toHaveBeenCalledTimes(1)
    expect(mockedDeleteWh.mock.calls[0]).toEqual([TOKEN, SALON_ID, 'wh-1'])
    expect(mockedPreview).toHaveBeenCalledTimes(1)
  })

  it('when previewScheduleImpact rejects: preview is called, DELETE is not, error shows in panel, Cancel closes without delete', async () => {
    mockedPreview.mockRejectedValue(new ApiError(502, 'Preview unavailable'))
    await renderPage()
    await click(buttonByText(container, 'Delete'))
    await settle()

    expect(mockedPreview).toHaveBeenCalledTimes(1)
    expect(mockedDeleteWh).not.toHaveBeenCalled()
    expect(previewPanel()).not.toBeNull()
    expect(previewPanel()?.querySelector('[role="alert"]')?.textContent).toContain(
      'Preview unavailable',
    )

    await click(buttonByText(previewPanel()!, 'Cancel'))
    await settle()

    expect(previewPanel()).toBeNull()
    expect(mockedDeleteWh).not.toHaveBeenCalled()
  })

  it('shows an error and closes the preview when DELETE fails', async () => {
    mockedDeleteWh.mockRejectedValue(new ApiError(500, 'Server exploded'))
    await renderPage()
    await click(buttonByText(container, 'Delete'))
    await settle()
    await click(buttonByText(previewPanel()!, 'Delete working hours'))
    await settle()

    expect(mockedDeleteWh).toHaveBeenCalledTimes(1)
    expect(previewPanel()).toBeNull()
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('Server exploded')
  })

  it('does not offer delete or preview to roles that cannot manage the schedule', async () => {
    setAuth('staff')
    await renderPage()

    expect(buttonByText(container, 'Delete')).toBeUndefined()
    expect(previewPanel()).toBeNull()
    expect(mockedPreview).not.toHaveBeenCalled()
    expect(mockedDeleteWh).not.toHaveBeenCalled()
  })

  it('regression: working-hours delete never uses window.confirm; create/update are not triggered', async () => {
    await renderPage()
    await click(buttonByText(container, 'Delete'))
    await settle()
    await click(buttonByText(previewPanel()!, 'Delete working hours'))
    await settle()

    expect(window.confirm).not.toHaveBeenCalled()
    expect(mockedDeleteWh).toHaveBeenCalledTimes(1)
    expect(vi.mocked(deleteBlockedPeriod)).not.toHaveBeenCalled()
    expect(vi.mocked(createWorkingHours)).not.toHaveBeenCalled()
    expect(vi.mocked(updateWorkingHours)).not.toHaveBeenCalled()
  })
})

function makeBp(overrides: Partial<BlockedPeriodItem> = {}): BlockedPeriodItem {
  return {
    id: 'bp-1',
    staff_id: null,
    starts_at: '2026-02-01T10:00:00+00:00',
    ends_at: '2026-02-01T12:00:00+00:00',
    reason: 'Holiday',
    block_type: 'holiday',
    created_by_user_id: null,
    created_at: '2026-01-01T00:00:00+00:00',
    updated_at: '2026-01-01T00:00:00+00:00',
    ...overrides,
  }
}

describe('AdminSchedulePage blocked period delete preview', () => {
  let container: HTMLDivElement
  let root: Root
  const mockedDeleteBp = vi.mocked(deleteBlockedPeriod)

  async function settle() {
    await act(async () => {
      await flushPromises()
      await flushPromises()
    })
  }

  async function renderPage() {
    await act(async () => {
      root.render(<AdminSchedulePage />)
      await flushPromises()
      await flushPromises()
    })
  }

  function buttonByText(scope: ParentNode, text: string): HTMLButtonElement | undefined {
    return Array.from(scope.querySelectorAll('button')).find(
      (b) => b.textContent?.trim() === text,
    ) as HTMLButtonElement | undefined
  }

  function bpSection(): HTMLElement {
    return container.querySelector('[aria-labelledby="admin-schedule-bp-heading"]') as HTMLElement
  }

  function previewPanel(): HTMLElement | null {
    return container.querySelector('.schedule-impact-preview')
  }

  async function click(el: HTMLElement | undefined | null) {
    expect(el).toBeTruthy()
    await act(async () => {
      el?.click()
      await flushPromises()
    })
  }

  async function openBpPreview() {
    await click(buttonByText(bpSection(), 'Delete'))
    await settle()
  }

  beforeEach(() => {
    ;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    vi.clearAllMocks()
    mockedPreview.mockReset()
    mockedFetchWh.mockReset()
    mockedFetchBp.mockReset()
    mockedDeleteBp.mockReset()
    mockedFetchStaff.mockReset()
    mockedFetchWh.mockResolvedValue([])
    mockedFetchBp.mockResolvedValue([makeBp()])
    mockedFetchStaff.mockResolvedValue([])
    mockedDeleteBp.mockResolvedValue(undefined)
    mockedPreview.mockResolvedValue(makeScheduleImpactPreviewResponse())
    setAuth('owner')
    vi.spyOn(window, 'confirm').mockImplementation(() => true)
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
    vi.restoreAllMocks()
  })

  it('Delete click opens the preview with a blocked_period.delete change, does not call DELETE or window.confirm, and disables row Delete', async () => {
    await renderPage()
    await openBpPreview()

    expect(previewPanel()).not.toBeNull()
    expect(mockedPreview).toHaveBeenCalledTimes(1)
    const [token, salonId, request] = mockedPreview.mock.calls[0]
    expect(token).toBe(TOKEN)
    expect(salonId).toBe(SALON_ID)
    expect(request.change).toEqual({
      kind: 'blocked_period.delete',
      blocked_period_id: 'bp-1',
    })
    expect(mockedDeleteBp).not.toHaveBeenCalled()
    expect(window.confirm).not.toHaveBeenCalled()
    expect(buttonByText(bpSection(), 'Delete')?.disabled).toBe(true)
  })

  it('shows the preview even with zero impacts and requires explicit confirm to DELETE', async () => {
    await renderPage()
    await openBpPreview()

    expect(previewPanel()?.textContent).toContain('No bookings would be affected')
    expect(mockedDeleteBp).not.toHaveBeenCalled()

    await click(buttonByText(previewPanel()!, 'Delete blocked period'))
    await settle()
    expect(mockedDeleteBp).toHaveBeenCalledTimes(1)
  })

  it('confirm calls deleteBlockedPeriod with token, salon id and snapshot id only (no fingerprint)', async () => {
    await renderPage()
    await openBpPreview()
    await click(buttonByText(previewPanel()!, 'Delete blocked period'))
    await settle()

    expect(mockedDeleteBp).toHaveBeenCalledTimes(1)
    expect(mockedDeleteBp.mock.calls[0]).toEqual([TOKEN, SALON_ID, 'bp-1'])
    expect(JSON.stringify(mockedDeleteBp.mock.calls[0])).not.toContain('f'.repeat(64))
    expect(mockedFetchBp.mock.calls.length).toBeGreaterThanOrEqual(2)
    expect(previewPanel()).toBeNull()
    expect(window.confirm).not.toHaveBeenCalled()
  })

  it('Cancel closes the preview, does not call DELETE, and re-enables row Delete', async () => {
    await renderPage()
    await openBpPreview()
    await click(buttonByText(previewPanel()!, 'Cancel'))
    await settle()

    expect(previewPanel()).toBeNull()
    expect(mockedDeleteBp).not.toHaveBeenCalled()
    expect(buttonByText(bpSection(), 'Delete')?.disabled).toBe(false)
  })

  it('confirm stays disabled until acknowledgement when impacts require it', async () => {
    mockedPreview.mockResolvedValue(impactfulResponse())
    await renderPage()
    await openBpPreview()

    const confirmBtn = buttonByText(previewPanel()!, 'Delete blocked period')
    expect(confirmBtn?.disabled).toBe(true)
    await click(confirmBtn)
    expect(mockedDeleteBp).not.toHaveBeenCalled()

    const checkbox = previewPanel()!.querySelector('input[type="checkbox"]') as HTMLInputElement
    await click(checkbox)
    expect(buttonByText(previewPanel()!, 'Delete blocked period')?.disabled).toBe(false)

    await click(buttonByText(previewPanel()!, 'Delete blocked period'))
    await settle()
    expect(mockedDeleteBp).toHaveBeenCalledTimes(1)
    expect(mockedDeleteBp.mock.calls[0]).toEqual([TOKEN, SALON_ID, 'bp-1'])
  })

  it('confirm uses the frozen snapshot, not live rows that change while the preview is open', async () => {
    await renderPage()
    await openBpPreview()
    expect(previewPanel()).not.toBeNull()

    // Live list changes underneath the open preview: re-applying filters reloads other rows.
    mockedFetchBp.mockResolvedValue([makeBp({ id: 'bp-2', reason: 'Replacement row' })])
    await click(buttonByText(bpSection(), 'Apply'))
    await settle()
    expect(bpSection().textContent).toContain('Replacement row')

    await click(buttonByText(previewPanel()!, 'Delete blocked period'))
    await settle()

    expect(mockedDeleteBp).toHaveBeenCalledTimes(1)
    expect(mockedDeleteBp.mock.calls[0]).toEqual([TOKEN, SALON_ID, 'bp-1'])
    expect(mockedPreview).toHaveBeenCalledTimes(1)
  })

  it('when previewScheduleImpact rejects: preview is called, DELETE is not, error shows in panel, Cancel closes without delete', async () => {
    mockedPreview.mockRejectedValue(new ApiError(502, 'Preview unavailable'))
    await renderPage()
    await openBpPreview()

    expect(mockedPreview).toHaveBeenCalledTimes(1)
    expect(mockedDeleteBp).not.toHaveBeenCalled()
    expect(previewPanel()).not.toBeNull()
    expect(previewPanel()?.querySelector('[role="alert"]')?.textContent).toContain(
      'Preview unavailable',
    )

    await click(buttonByText(previewPanel()!, 'Cancel'))
    await settle()

    expect(previewPanel()).toBeNull()
    expect(mockedDeleteBp).not.toHaveBeenCalled()
  })

  it('shows an error and closes the preview when DELETE fails', async () => {
    mockedDeleteBp.mockRejectedValue(new ApiError(500, 'Server exploded'))
    await renderPage()
    await openBpPreview()
    await click(buttonByText(previewPanel()!, 'Delete blocked period'))
    await settle()

    expect(mockedDeleteBp).toHaveBeenCalledTimes(1)
    expect(previewPanel()).toBeNull()
    expect(bpSection().querySelector('[role="alert"]')?.textContent).toContain('Server exploded')
  })

  it('does not offer delete or preview to roles that cannot manage the schedule', async () => {
    setAuth('staff')
    await renderPage()

    expect(buttonByText(bpSection(), 'Delete')).toBeUndefined()
    expect(previewPanel()).toBeNull()
    expect(mockedPreview).not.toHaveBeenCalled()
    expect(mockedDeleteBp).not.toHaveBeenCalled()
    expect(window.confirm).not.toHaveBeenCalled()
  })
})

describe('AdminSchedulePage working hours create preview', () => {
  let container: HTMLDivElement
  let root: Root
  let clearAuthAndRedirect: ReturnType<typeof vi.fn>
  const mockedCreateWh = vi.mocked(createWorkingHours)
  const mockedDeleteBp = vi.mocked(deleteBlockedPeriod)

  async function settle() {
    await act(async () => {
      await flushPromises()
      await flushPromises()
    })
  }

  async function renderPage() {
    await act(async () => {
      root.render(<AdminSchedulePage />)
      await flushPromises()
      await flushPromises()
    })
  }

  function buttonByText(scope: ParentNode, text: string): HTMLButtonElement | undefined {
    return Array.from(scope.querySelectorAll('button')).find(
      (b) => b.textContent?.trim() === text,
    ) as HTMLButtonElement | undefined
  }

  function whSection(): HTMLElement {
    return container.querySelector('[aria-labelledby="admin-schedule-wh-heading"]') as HTMLElement
  }

  function bpSection(): HTMLElement {
    return container.querySelector('[aria-labelledby="admin-schedule-bp-heading"]') as HTMLElement
  }

  function whCreateForm(): HTMLFormElement {
    return whSection().querySelector('form.admin-schedule__form--create') as HTMLFormElement
  }

  function panels(): HTMLElement[] {
    return Array.from(container.querySelectorAll('.schedule-impact-preview'))
  }

  function whPanel(): HTMLElement | null {
    return whSection().querySelector('.schedule-impact-preview')
  }

  function bpPanel(): HTMLElement | null {
    return bpSection().querySelector('.schedule-impact-preview')
  }

  function input(id: string): HTMLInputElement {
    return container.querySelector(`#${id}`) as HTMLInputElement
  }

  async function click(el: HTMLElement | undefined | null) {
    expect(el).toBeTruthy()
    await act(async () => {
      el?.click()
      await flushPromises()
    })
  }

  async function setValue(el: HTMLInputElement | HTMLSelectElement, value: string) {
    await act(async () => {
      const proto =
        el instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype
      Object.getOwnPropertyDescriptor(proto, 'value')?.set?.call(el, value)
      el.dispatchEvent(new Event(el instanceof HTMLSelectElement ? 'change' : 'input', { bubbles: true }))
      await flushPromises()
    })
  }

  async function fillTimes(start = '09:00', end = '17:00') {
    await setValue(input('wh-create-start'), start)
    await setValue(input('wh-create-end'), end)
  }

  async function submitCreate() {
    await click(buttonByText(whCreateForm(), 'Create'))
    await settle()
  }

  async function openCreatePreview() {
    await fillTimes()
    await submitCreate()
  }

  beforeEach(() => {
    ;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    vi.clearAllMocks()
    mockedPreview.mockReset()
    mockedFetchWh.mockReset()
    mockedFetchBp.mockReset()
    mockedCreateWh.mockReset()
    mockedDeleteWh.mockReset()
    mockedDeleteBp.mockReset()
    mockedFetchStaff.mockReset()
    mockedFetchWh.mockResolvedValue([makeRow()])
    mockedFetchBp.mockResolvedValue([makeBp()])
    mockedFetchStaff.mockResolvedValue([])
    mockedCreateWh.mockResolvedValue(makeRow({ id: 'wh-new' }))
    mockedDeleteWh.mockResolvedValue(undefined)
    mockedDeleteBp.mockResolvedValue(undefined)
    mockedPreview.mockResolvedValue(makeScheduleImpactPreviewResponse())
    clearAuthAndRedirect = setAuth('owner')
    vi.spyOn(window, 'confirm').mockImplementation(() => true)
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
    vi.restoreAllMocks()
  })

  it('pre-check: empty times show a clear message and neither preview nor create is called', async () => {
    await renderPage()
    await submitCreate()

    expect(whSection().textContent).toContain('Enter both a start time and an end time.')
    expect(mockedPreview).not.toHaveBeenCalled()
    expect(mockedCreateWh).not.toHaveBeenCalled()
    expect(whPanel()).toBeNull()

    await setValue(input('wh-create-start'), '09:00')
    await submitCreate()
    expect(whSection().textContent).toContain('Enter both a start time and an end time.')
    expect(mockedPreview).not.toHaveBeenCalled()
    expect(mockedCreateWh).not.toHaveBeenCalled()
  })

  it('pre-check: start equal to or after end shows a clear message and calls nothing', async () => {
    await renderPage()
    await fillTimes('17:00', '09:00')
    await submitCreate()

    expect(whSection().textContent).toContain('Start time must be before end time.')
    expect(mockedPreview).not.toHaveBeenCalled()
    expect(mockedCreateWh).not.toHaveBeenCalled()
    expect(whPanel()).toBeNull()

    await fillTimes('10:00', '10:00')
    await submitCreate()
    expect(whSection().textContent).toContain('Start time must be before end time.')
    expect(mockedPreview).not.toHaveBeenCalled()
    expect(mockedCreateWh).not.toHaveBeenCalled()
  })

  it('a valid pre-check clears the earlier message and opens the preview', async () => {
    await renderPage()
    await fillTimes('17:00', '09:00')
    await submitCreate()
    expect(whSection().textContent).toContain('Start time must be before end time.')

    await fillTimes('09:00', '17:00')
    await submitCreate()
    expect(whSection().textContent).not.toContain('Start time must be before end time.')
    expect(whPanel()).not.toBeNull()
    expect(mockedPreview).toHaveBeenCalledTimes(1)
  })

  it('submit opens a working_hours.create preview, does not POST, and locks form, scope and row actions', async () => {
    await renderPage()
    await openCreatePreview()

    expect(whPanel()).not.toBeNull()
    expect(mockedPreview).toHaveBeenCalledTimes(1)
    const [token, salonId, request] = mockedPreview.mock.calls[0]
    expect(token).toBe(TOKEN)
    expect(salonId).toBe(SALON_ID)
    expect(request.change).toEqual({
      kind: 'working_hours.create',
      staff_id: null,
      day_of_week: 0,
      start_time: '09:00:00',
      end_time: '17:00:00',
      effective_from: null,
      effective_to: null,
    })
    expect(mockedCreateWh).not.toHaveBeenCalled()
    expect(window.confirm).not.toHaveBeenCalled()

    for (const id of [
      'wh-create-day',
      'wh-create-start',
      'wh-create-end',
      'wh-create-effective-from',
      'wh-create-effective-to',
    ]) {
      expect((container.querySelector(`#${id}`) as HTMLInputElement).disabled).toBe(true)
    }
    expect(buttonByText(whCreateForm(), 'Create')?.disabled).toBe(true)
    expect((whSection().querySelector('select') as HTMLSelectElement).disabled).toBe(true)
    const table = whSection().querySelector('table') as HTMLElement
    expect(buttonByText(table, 'Edit')?.disabled).toBe(true)
    expect(buttonByText(table, 'Delete')?.disabled).toBe(true)
  })

  it('uses the selected staff scope in the snapshot change', async () => {
    mockedFetchStaff.mockResolvedValue([
      { id: 'staff-9', display_name: 'Bob' } as unknown as Awaited<
        ReturnType<typeof fetchAdminStaff>
      >[number],
    ])
    await renderPage()
    await setValue(whSection().querySelector('select') as HTMLSelectElement, 'staff-9')
    await settle()
    await openCreatePreview()

    expect(mockedPreview.mock.calls[0][2].change).toMatchObject({
      kind: 'working_hours.create',
      staff_id: 'staff-9',
    })
    await click(buttonByText(whPanel()!, 'Create working hours'))
    await settle()
    expect(mockedCreateWh.mock.calls[0][2]).toMatchObject({ staff_id: 'staff-9' })
  })

  it('shows the preview even with zero impacts and requires explicit confirm to POST', async () => {
    await renderPage()
    await openCreatePreview()

    expect(whPanel()?.textContent).toContain('No bookings would be affected')
    expect(mockedCreateWh).not.toHaveBeenCalled()

    await click(buttonByText(whPanel()!, 'Create working hours'))
    await settle()
    expect(mockedCreateWh).toHaveBeenCalledTimes(1)
  })

  it('confirm calls createWorkingHours with token, snapshot salon id and snapshot body only (no fingerprint)', async () => {
    await renderPage()
    await openCreatePreview()
    const calls = mockedFetchWh.mock.calls.length
    await click(buttonByText(whPanel()!, 'Create working hours'))
    await settle()

    expect(mockedCreateWh).toHaveBeenCalledTimes(1)
    expect(mockedCreateWh.mock.calls[0]).toEqual([
      TOKEN,
      SALON_ID,
      {
        staff_id: null,
        day_of_week: 0,
        start_time: '09:00:00',
        end_time: '17:00:00',
        effective_from: null,
        effective_to: null,
      },
    ])
    const serialized = JSON.stringify(mockedCreateWh.mock.calls[0])
    expect(serialized).not.toContain('f'.repeat(64))
    expect(serialized).not.toContain('fingerprint')
    expect(Object.keys(mockedCreateWh.mock.calls[0][2])).not.toContain('kind')
    expect(mockedFetchWh.mock.calls.length).toBeGreaterThan(calls)
    expect(whPanel()).toBeNull()
    expect(input('wh-create-start').value).toBe('')
    expect(input('wh-create-start').disabled).toBe(false)
    expect(window.confirm).not.toHaveBeenCalled()
  })

  it('preview and create use the same frozen snapshot even if the live form and scope change afterwards', async () => {
    mockedFetchStaff.mockResolvedValue([
      { id: 'staff-9', display_name: 'Bob' } as unknown as Awaited<
        ReturnType<typeof fetchAdminStaff>
      >[number],
    ])
    await renderPage()
    await openCreatePreview()
    const previewedChange = mockedPreview.mock.calls[0][2].change

    // Force live state changes underneath the open preview (controls are disabled in the UI).
    await setValue(input('wh-create-start'), '11:00')
    await setValue(input('wh-create-end'), '12:00')
    await setValue(whSection().querySelector('select') as HTMLSelectElement, 'staff-9')
    await settle()
    expect(whPanel()).not.toBeNull()

    await click(buttonByText(whPanel()!, 'Create working hours'))
    await settle()

    expect(mockedPreview).toHaveBeenCalledTimes(1)
    expect(mockedCreateWh).toHaveBeenCalledTimes(1)
    expect(mockedCreateWh.mock.calls[0]).toEqual([
      TOKEN,
      SALON_ID,
      {
        staff_id: null,
        day_of_week: 0,
        start_time: '09:00:00',
        end_time: '17:00:00',
        effective_from: null,
        effective_to: null,
      },
    ])
    const { kind, ...previewedBody } = previewedChange as Record<string, unknown>
    expect(kind).toBe('working_hours.create')
    expect(mockedCreateWh.mock.calls[0][2]).toEqual(previewedBody)
  })

  it('confirm does not call create when the salon changed while the preview was open', async () => {
    await renderPage()
    await openCreatePreview()

    mockedUseAuth.mockReturnValue({
      session: { token: TOKEN, salon: { salon_id: 'salon-2', role: 'owner' } },
      clearAuthAndRedirect,
    } as unknown as ReturnType<typeof useAuth>)
    await renderPage()
    await click(buttonByText(whPanel()!, 'Create working hours'))
    await settle()

    expect(mockedCreateWh).not.toHaveBeenCalled()
  })

  it('Cancel closes the preview, does not POST, keeps the form values and unlocks the form', async () => {
    await renderPage()
    await openCreatePreview()
    await click(buttonByText(whPanel()!, 'Cancel'))
    await settle()

    expect(whPanel()).toBeNull()
    expect(mockedCreateWh).not.toHaveBeenCalled()
    expect(input('wh-create-start').value).toBe('09:00')
    expect(input('wh-create-end').value).toBe('17:00')
    expect(input('wh-create-start').disabled).toBe(false)
    expect(buttonByText(whCreateForm(), 'Create')?.disabled).toBe(false)
    expect((whSection().querySelector('select') as HTMLSelectElement).disabled).toBe(false)
    expect(buttonByText(whSection().querySelector('table')!, 'Delete')?.disabled).toBe(false)
  })

  it('a reopened preview gets a fresh snapshot and a new request', async () => {
    await renderPage()
    await openCreatePreview()
    await click(buttonByText(whPanel()!, 'Cancel'))
    await fillTimes('08:00', '12:00')
    await submitCreate()

    expect(mockedPreview).toHaveBeenCalledTimes(2)
    expect(mockedPreview.mock.calls[1][2].change).toMatchObject({
      start_time: '08:00:00',
      end_time: '12:00:00',
    })
    await click(buttonByText(whPanel()!, 'Create working hours'))
    await settle()
    expect(mockedCreateWh.mock.calls[0][2]).toMatchObject({
      start_time: '08:00:00',
      end_time: '12:00:00',
    })
  })

  it('confirm stays disabled until acknowledgement when impacts require it', async () => {
    mockedPreview.mockResolvedValue(impactfulResponse())
    await renderPage()
    await openCreatePreview()

    const confirmBtn = buttonByText(whPanel()!, 'Create working hours')
    expect(confirmBtn?.disabled).toBe(true)
    await click(confirmBtn)
    expect(mockedCreateWh).not.toHaveBeenCalled()

    await click(whPanel()!.querySelector('input[type="checkbox"]') as HTMLInputElement)
    expect(buttonByText(whPanel()!, 'Create working hours')?.disabled).toBe(false)
    await click(buttonByText(whPanel()!, 'Create working hours'))
    await settle()
    expect(mockedCreateWh).toHaveBeenCalledTimes(1)
  })

  it('preview 401 shows a panel error, does not redirect and does not create; Cancel closes', async () => {
    mockedPreview.mockRejectedValue(new ApiError(401, 'Session expired'))
    await renderPage()
    await openCreatePreview()

    expect(mockedPreview).toHaveBeenCalledTimes(1)
    expect(whPanel()?.querySelector('[role="alert"]')?.textContent).toContain('Session expired')
    expect(clearAuthAndRedirect).not.toHaveBeenCalled()
    expect(buttonByText(whPanel()!, 'Create working hours')?.disabled).toBe(true)
    expect(mockedCreateWh).not.toHaveBeenCalled()

    await click(buttonByText(whPanel()!, 'Cancel'))
    expect(whPanel()).toBeNull()
    expect(clearAuthAndRedirect).not.toHaveBeenCalled()
    expect(mockedCreateWh).not.toHaveBeenCalled()
  })

  it('when previewScheduleImpact rejects: error shows in panel, create is not called, Cancel closes', async () => {
    mockedPreview.mockRejectedValue(new ApiError(502, 'Preview unavailable'))
    await renderPage()
    await openCreatePreview()

    expect(mockedCreateWh).not.toHaveBeenCalled()
    expect(whPanel()?.querySelector('[role="alert"]')?.textContent).toContain(
      'Preview unavailable',
    )
    await click(buttonByText(whPanel()!, 'Cancel'))
    expect(whPanel()).toBeNull()
    expect(mockedCreateWh).not.toHaveBeenCalled()
  })

  it('shows an error, closes the preview and keeps the form when the POST fails', async () => {
    mockedCreateWh.mockRejectedValue(new ApiError(500, 'Server exploded'))
    await renderPage()
    await openCreatePreview()
    await click(buttonByText(whPanel()!, 'Create working hours'))
    await settle()

    expect(mockedCreateWh).toHaveBeenCalledTimes(1)
    expect(whPanel()).toBeNull()
    expect(whSection().querySelector('[role="alert"]')?.textContent).toContain('Server exploded')
    expect(input('wh-create-start').value).toBe('09:00')
  })

  it('a 401 from the create POST still redirects via clearAuthAndRedirect', async () => {
    mockedCreateWh.mockRejectedValue(new ApiError(401, 'Unauthorized'))
    await renderPage()
    await openCreatePreview()
    await click(buttonByText(whPanel()!, 'Create working hours'))
    await settle()

    expect(clearAuthAndRedirect).toHaveBeenCalledTimes(1)
  })

  it('does not offer the create form or preview to roles that cannot manage the schedule', async () => {
    setAuth('staff')
    await renderPage()

    expect(whSection().querySelector('form.admin-schedule__form--create')).toBeNull()
    expect(whPanel()).toBeNull()
    expect(mockedPreview).not.toHaveBeenCalled()
    expect(mockedCreateWh).not.toHaveBeenCalled()
  })

  it('mutual block: WH delete preview blocks opening the WH create preview', async () => {
    await renderPage()
    await fillTimes()
    await click(buttonByText(whSection().querySelector('table')!, 'Delete'))
    await settle()
    expect(whSection().querySelectorAll('.schedule-impact-preview')).toHaveLength(1)
    expect(mockedPreview).toHaveBeenCalledTimes(1)
    expect(buttonByText(whCreateForm(), 'Create')?.disabled).toBe(true)

    // Even a programmatic submit must not open a second WH preview.
    await act(async () => {
      whCreateForm().requestSubmit()
      await flushPromises()
    })
    await settle()
    expect(whSection().querySelectorAll('.schedule-impact-preview')).toHaveLength(1)
    expect(mockedPreview).toHaveBeenCalledTimes(1)
    expect(mockedCreateWh).not.toHaveBeenCalled()
  })

  it('mutual block: WH create preview blocks opening the WH delete preview', async () => {
    await renderPage()
    await openCreatePreview()
    const deleteBtn = buttonByText(whSection().querySelector('table')!, 'Delete')
    expect(deleteBtn?.disabled).toBe(true)
    await click(deleteBtn)
    await settle()

    expect(whSection().querySelectorAll('.schedule-impact-preview')).toHaveLength(1)
    expect(mockedPreview).toHaveBeenCalledTimes(1)
    expect(mockedPreview.mock.calls[0][2].change).toMatchObject({ kind: 'working_hours.create' })
    expect(mockedDeleteWh).not.toHaveBeenCalled()
  })

  it('dual panel: BP delete preview can be open together with the WH create preview and both confirm independently', async () => {
    await renderPage()
    await openCreatePreview()
    await click(buttonByText(bpSection(), 'Delete'))
    await settle()

    expect(panels()).toHaveLength(2)
    expect(whPanel()).not.toBeNull()
    expect(bpPanel()).not.toBeNull()
    expect(mockedPreview).toHaveBeenCalledTimes(2)
    expect(mockedPreview.mock.calls[0][2].change.kind).toBe('working_hours.create')
    expect(mockedPreview.mock.calls[1][2].change).toEqual({
      kind: 'blocked_period.delete',
      blocked_period_id: 'bp-1',
    })

    await click(buttonByText(bpPanel()!, 'Delete blocked period'))
    await settle()
    expect(mockedDeleteBp.mock.calls[0]).toEqual([TOKEN, SALON_ID, 'bp-1'])
    expect(mockedCreateWh).not.toHaveBeenCalled()
    expect(whPanel()).not.toBeNull()
    expect(bpPanel()).toBeNull()

    await click(buttonByText(whPanel()!, 'Create working hours'))
    await settle()
    expect(mockedCreateWh).toHaveBeenCalledTimes(1)
    expect(mockedDeleteBp).toHaveBeenCalledTimes(1)
    expect(panels()).toHaveLength(0)
  })

  it('dual panel: WH create preview can be opened while a BP delete preview is already open', async () => {
    await renderPage()
    await click(buttonByText(bpSection(), 'Delete'))
    await settle()
    await openCreatePreview()

    expect(panels()).toHaveLength(2)
    expect(buttonByText(bpSection(), 'Delete')?.disabled).toBe(true)
    await click(buttonByText(whPanel()!, 'Cancel'))
    expect(whPanel()).toBeNull()
    expect(bpPanel()).not.toBeNull()
    expect(mockedCreateWh).not.toHaveBeenCalled()
    expect(mockedDeleteBp).not.toHaveBeenCalled()
  })

  it('regression: WH delete preview still deletes only after confirm, without create or window.confirm', async () => {
    await renderPage()
    await click(buttonByText(whSection().querySelector('table')!, 'Delete'))
    await settle()
    expect(mockedDeleteWh).not.toHaveBeenCalled()
    await click(buttonByText(whPanel()!, 'Delete working hours'))
    await settle()

    expect(mockedDeleteWh.mock.calls[0]).toEqual([TOKEN, SALON_ID, 'wh-1'])
    expect(mockedCreateWh).not.toHaveBeenCalled()
    expect(window.confirm).not.toHaveBeenCalled()
  })

  it('regression: BP delete preview still deletes only after confirm, without create or window.confirm', async () => {
    await renderPage()
    await click(buttonByText(bpSection(), 'Delete'))
    await settle()
    expect(mockedDeleteBp).not.toHaveBeenCalled()
    await click(buttonByText(bpPanel()!, 'Delete blocked period'))
    await settle()

    expect(mockedDeleteBp.mock.calls[0]).toEqual([TOKEN, SALON_ID, 'bp-1'])
    expect(mockedCreateWh).not.toHaveBeenCalled()
    expect(window.confirm).not.toHaveBeenCalled()
  })
})
