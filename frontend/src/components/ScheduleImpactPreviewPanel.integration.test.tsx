/**
 * @vitest-environment jsdom
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createRoot, type Root } from 'react-dom/client'
import { act } from 'react'
import { ScheduleImpactPreviewPanel } from './ScheduleImpactPreviewPanel'
import { previewScheduleImpact } from '../api/schedule'
import { makeScheduleImpactPreviewResponse } from './scheduleImpactPreviewFixtures'

vi.mock('../api/schedule', () => ({
  previewScheduleImpact: vi.fn(),
  createWorkingHours: vi.fn(),
  updateWorkingHours: vi.fn(),
  deleteWorkingHours: vi.fn(),
  createBlockedPeriod: vi.fn(),
  updateBlockedPeriod: vi.fn(),
  deleteBlockedPeriod: vi.fn(),
}))

const mockedPreview = vi.mocked(previewScheduleImpact)

function flushPromises() {
  return new Promise<void>((resolve) => {
    setTimeout(resolve, 0)
  })
}

describe('ScheduleImpactPreviewPanel integration', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    mockedPreview.mockReset()
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
  })

  it('Cancel calls onCancel and does not invoke CRUD APIs', async () => {
    mockedPreview.mockResolvedValue(makeScheduleImpactPreviewResponse())
    const onCancel = vi.fn()
    const onConfirm = vi.fn()
    await act(async () => {
      root.render(
        <ScheduleImpactPreviewPanel
          token="t"
          salonId="salon"
          change={{
            kind: 'working_hours.delete',
            working_hours_id: 'wh-1',
          }}
          onCancel={onCancel}
          onConfirm={onConfirm}
        />,
      )
      await flushPromises()
    })
    const cancelBtn = Array.from(container.querySelectorAll('button')).find(
      (b) => b.textContent === 'Cancel',
    )
    expect(cancelBtn).toBeTruthy()
    await act(async () => {
      cancelBtn?.click()
    })
    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(onConfirm).not.toHaveBeenCalled()
    const scheduleApi = await import('../api/schedule')
    expect(scheduleApi.deleteWorkingHours).not.toHaveBeenCalled()
    expect(scheduleApi.createWorkingHours).not.toHaveBeenCalled()
  })

  it('Confirm stays disabled until acknowledgement when required', async () => {
    mockedPreview.mockResolvedValue(
      makeScheduleImpactPreviewResponse({
        counts: { total_impacted: 1, by_reason: {} },
        impacts: [
          {
            booking_id: 'b-1',
            status: 'confirmed',
            is_in_progress: false,
            starts_at: '2026-01-01T10:00:00+00:00',
            ends_at: '2026-01-01T11:00:00+00:00',
            staff_id: 's1',
            service_id: 'v1',
            customer_name: 'A',
            service_name: 'S',
            reasons: ['outside_availability'],
          },
        ],
        pagination: {
          offset: 0,
          limit: 50,
          returned: 1,
          total_impacted: 1,
          has_more: false,
        },
        commit_policy: {
          allow_commit_with_impacts: true,
          requires_acknowledgement: true,
        },
      }),
    )
    const onConfirm = vi.fn()
    await act(async () => {
      root.render(
        <ScheduleImpactPreviewPanel
          token="t"
          salonId="salon"
          change={{
            kind: 'working_hours.delete',
            working_hours_id: 'wh-1',
          }}
          onCancel={() => {}}
          onConfirm={onConfirm}
        />,
      )
      await flushPromises()
    })
    const confirmBtn = Array.from(container.querySelectorAll('button')).find(
      (b) => b.textContent === 'Continue',
    )
    expect(confirmBtn?.disabled).toBe(true)
    const checkbox = container.querySelector(
      'input[type="checkbox"]',
    ) as HTMLInputElement
    await act(async () => {
      checkbox.click()
      await flushPromises()
    })
    expect(confirmBtn?.disabled).toBe(false)
    await act(async () => {
      confirmBtn?.click()
    })
    expect(onConfirm).toHaveBeenCalledTimes(1)
    const payload = onConfirm.mock.calls[0]?.[0]
    expect(payload?.fingerprint).toHaveLength(64)
    expect(payload?.acknowledgementChecked).toBe(true)
    expect(payload?.impacts).toHaveLength(1)
    expect(payload?.response.counts.total_impacted).toBe(1)
    expect(payload?.change).toEqual({
      kind: 'working_hours.delete',
      working_hours_id: 'wh-1',
    })
  })
})
