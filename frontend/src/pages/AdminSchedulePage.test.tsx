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
import type { WorkingHoursItem } from '../types/schedule'

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

  it('leaves other flows unchanged: blocked-period delete still uses window.confirm and never previews', async () => {
    mockedFetchBp.mockResolvedValue([
      {
        id: 'bp-1',
        staff_id: null,
        starts_at: '2026-02-01T10:00:00+00:00',
        ends_at: '2026-02-01T12:00:00+00:00',
        reason: 'Holiday',
        block_type: 'holiday',
        created_by_user_id: null,
        created_at: '2026-01-01T00:00:00+00:00',
        updated_at: '2026-01-01T00:00:00+00:00',
      },
    ])
    vi.mocked(deleteBlockedPeriod).mockResolvedValue(undefined)
    await renderPage()

    const bpSection = container.querySelector('[aria-labelledby="admin-schedule-bp-heading"]')!
    await click(buttonByText(bpSection, 'Delete'))
    await settle()

    expect(window.confirm).toHaveBeenCalledTimes(1)
    expect(deleteBlockedPeriod).toHaveBeenCalledWith(TOKEN, SALON_ID, 'bp-1')
    expect(mockedPreview).not.toHaveBeenCalled()
    expect(vi.mocked(createWorkingHours)).not.toHaveBeenCalled()
    expect(vi.mocked(updateWorkingHours)).not.toHaveBeenCalled()
  })
})
