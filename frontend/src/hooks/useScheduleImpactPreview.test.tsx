/**
 * @vitest-environment jsdom
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createRoot, type Root } from 'react-dom/client'
import { act } from 'react'
import { useScheduleImpactPreview } from './useScheduleImpactPreview'
import { previewScheduleImpact } from '../api/schedule'
import { makeScheduleImpactPreviewResponse } from '../components/scheduleImpactPreviewFixtures'

vi.mock('../api/schedule', () => ({
  previewScheduleImpact: vi.fn(),
}))

const mockedPreview = vi.mocked(previewScheduleImpact)

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function flushPromises() {
  return new Promise<void>((resolve) => {
    setTimeout(resolve, 0)
  })
}

describe('useScheduleImpactPreview', () => {
  let container: HTMLDivElement
  let root: Root
  let latest: ReturnType<typeof useScheduleImpactPreview> | null

  function Probe(props: Parameters<typeof useScheduleImpactPreview>[0]) {
    latest = useScheduleImpactPreview(props)
    return null
  }

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    latest = null
    mockedPreview.mockReset()
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
  })

  it('loads preview on mount and stores fingerprint', async () => {
    mockedPreview.mockResolvedValue(
      makeScheduleImpactPreviewResponse({
        impact_fingerprint: 'abc',
      }),
    )
    await act(async () => {
      root.render(
        <Probe
          token="t"
          salonId="salon"
          change={{
            kind: 'working_hours.delete',
            working_hours_id: 'wh-1',
          }}
        />,
      )
      await flushPromises()
    })
    expect(mockedPreview).toHaveBeenCalledTimes(1)
    expect(latest?.fingerprint).toBe('abc')
    expect(latest?.loading).toBe(false)
    expect(latest?.error).toBe(null)
  })

  it('retries preview from offset zero', async () => {
    mockedPreview
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValueOnce(makeScheduleImpactPreviewResponse())
    await act(async () => {
      root.render(
        <Probe
          token="t"
          salonId="salon"
          change={{
            kind: 'working_hours.delete',
            working_hours_id: 'wh-1',
          }}
        />,
      )
      await flushPromises()
    })
    expect(latest?.error).toBeTruthy()
    await act(async () => {
      latest?.retry()
      await flushPromises()
    })
    expect(mockedPreview).toHaveBeenCalledTimes(2)
    expect(latest?.error).toBe(null)
  })

  it('loads next page when loadMore is called', async () => {
    mockedPreview
      .mockResolvedValueOnce(
        makeScheduleImpactPreviewResponse({
          counts: { total_impacted: 2, by_reason: {} },
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
              reasons: [],
            },
          ],
          pagination: {
            offset: 0,
            limit: 1,
            returned: 1,
            total_impacted: 2,
            has_more: true,
          },
        }),
      )
      .mockResolvedValueOnce(
        makeScheduleImpactPreviewResponse({
          counts: { total_impacted: 2, by_reason: {} },
          impacts: [
            {
              booking_id: 'b-2',
              status: 'confirmed',
              is_in_progress: false,
              starts_at: '2026-01-02T10:00:00+00:00',
              ends_at: '2026-01-02T11:00:00+00:00',
              staff_id: 's1',
              service_id: 'v1',
              customer_name: 'B',
              service_name: 'S',
              reasons: [],
            },
          ],
          pagination: {
            offset: 1,
            limit: 1,
            returned: 1,
            total_impacted: 2,
            has_more: false,
          },
        }),
      )
    await act(async () => {
      root.render(
        <Probe
          token="t"
          salonId="salon"
          change={{
            kind: 'working_hours.delete',
            working_hours_id: 'wh-1',
          }}
          impactLimit={1}
        />,
      )
      await flushPromises()
    })
    await act(async () => {
      latest?.loadMore()
      await flushPromises()
    })
    expect(mockedPreview).toHaveBeenCalledTimes(2)
    expect(mockedPreview.mock.calls[1]?.[2]).toMatchObject({ impact_offset: 1 })
    expect(latest?.impacts.map((r) => r.booking_id)).toEqual(['b-1', 'b-2'])
  })

  it('keeps first-page fingerprint after load more', async () => {
    const firstFingerprint = '1'.repeat(64)
    mockedPreview
      .mockResolvedValueOnce(
        makeScheduleImpactPreviewResponse({
          impact_fingerprint: firstFingerprint,
          counts: { total_impacted: 2, by_reason: {} },
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
              reasons: [],
            },
          ],
          pagination: {
            offset: 0,
            limit: 1,
            returned: 1,
            total_impacted: 2,
            has_more: true,
          },
        }),
      )
      .mockResolvedValueOnce(
        makeScheduleImpactPreviewResponse({
          impact_fingerprint: '2'.repeat(64),
          pagination: {
            offset: 1,
            limit: 1,
            returned: 1,
            total_impacted: 2,
            has_more: false,
          },
          impacts: [
            {
              booking_id: 'b-2',
              status: 'confirmed',
              is_in_progress: false,
              starts_at: '2026-01-02T10:00:00+00:00',
              ends_at: '2026-01-02T11:00:00+00:00',
              staff_id: 's1',
              service_id: 'v1',
              customer_name: 'B',
              service_name: 'S',
              reasons: [],
            },
          ],
        }),
      )
    await act(async () => {
      root.render(
        <Probe
          token="t"
          salonId="salon"
          change={{
            kind: 'working_hours.delete',
            working_hours_id: 'wh-1',
          }}
          impactLimit={1}
        />,
      )
      await flushPromises()
    })
    await act(async () => {
      latest?.loadMore()
      await flushPromises()
    })
    expect(latest?.fingerprint).toBe(firstFingerprint)
    expect(latest?.response?.impact_fingerprint).toBe(firstFingerprint)
    expect(latest?.response?.pagination.has_more).toBe(false)
  })

  it('clears loading when superseded initial request finishes', async () => {
    const slow = deferred<ReturnType<typeof makeScheduleImpactPreviewResponse>>()
    mockedPreview
      .mockReturnValueOnce(slow.promise)
      .mockResolvedValueOnce(makeScheduleImpactPreviewResponse())
    await act(async () => {
      root.render(
        <Probe
          token="t"
          salonId="salon"
          change={{
            kind: 'working_hours.delete',
            working_hours_id: 'wh-1',
          }}
        />,
      )
    })
    expect(latest?.loading).toBe(true)
    await act(async () => {
      latest?.retry()
      await flushPromises()
    })
    expect(latest?.loading).toBe(false)
    await act(async () => {
      slow.resolve(makeScheduleImpactPreviewResponse({ impact_fingerprint: 'stale' }))
      await flushPromises()
    })
    expect(latest?.loading).toBe(false)
    expect(latest?.fingerprint).not.toBe('stale')
  })

  it('ignores stale load-more after retry or change supersede it', async () => {
    const slowMore = deferred<ReturnType<typeof makeScheduleImpactPreviewResponse>>()
    const firstPageImpact = {
      booking_id: 'b-1',
      status: 'confirmed' as const,
      is_in_progress: false,
      starts_at: '2026-01-01T10:00:00+00:00',
      ends_at: '2026-01-01T11:00:00+00:00',
      staff_id: 's1',
      service_id: 'v1',
      customer_name: 'A',
      service_name: 'S',
      reasons: [],
    }
    const stalePageImpact = {
      booking_id: 'b-stale',
      status: 'confirmed' as const,
      is_in_progress: false,
      starts_at: '2026-01-02T10:00:00+00:00',
      ends_at: '2026-01-02T11:00:00+00:00',
      staff_id: 's1',
      service_id: 'v1',
      customer_name: 'Stale',
      service_name: 'S',
      reasons: [],
    }

    mockedPreview
      .mockResolvedValueOnce(
        makeScheduleImpactPreviewResponse({
          counts: { total_impacted: 2, by_reason: {} },
          impacts: [firstPageImpact],
          pagination: {
            offset: 0,
            limit: 1,
            returned: 1,
            total_impacted: 2,
            has_more: true,
          },
        }),
      )
      .mockReturnValueOnce(slowMore.promise)
      .mockResolvedValueOnce(
        makeScheduleImpactPreviewResponse({
          impact_fingerprint: 'fresh-after-retry',
          impacts: [],
        }),
      )

    await act(async () => {
      root.render(
        <Probe
          token="t"
          salonId="salon"
          change={{
            kind: 'working_hours.delete',
            working_hours_id: 'wh-1',
          }}
          impactLimit={1}
        />,
      )
      await flushPromises()
    })
    expect(latest?.impacts.map((r) => r.booking_id)).toEqual(['b-1'])

    await act(async () => {
      latest?.loadMore()
    })
    expect(latest?.loadingMore).toBe(true)

    await act(async () => {
      latest?.retry()
      await flushPromises()
    })
    expect(latest?.loadingMore).toBe(false)
    expect(latest?.fingerprint).toBe('fresh-after-retry')
    expect(latest?.impacts).toEqual([])

    await act(async () => {
      slowMore.resolve(
        makeScheduleImpactPreviewResponse({
          impacts: [stalePageImpact],
          pagination: {
            offset: 1,
            limit: 1,
            returned: 1,
            total_impacted: 2,
            has_more: false,
          },
        }),
      )
      await flushPromises()
    })

    expect(latest?.loadingMore).toBe(false)
    expect(latest?.impacts.map((r) => r.booking_id)).toEqual([])
    expect(latest?.response?.pagination.has_more).toBe(false)
  })

  it('sets loadMoreError without clearing impacts', async () => {
    mockedPreview
      .mockResolvedValueOnce(
        makeScheduleImpactPreviewResponse({
          counts: { total_impacted: 2, by_reason: {} },
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
              reasons: [],
            },
          ],
          pagination: {
            offset: 0,
            limit: 1,
            returned: 1,
            total_impacted: 2,
            has_more: true,
          },
        }),
      )
      .mockRejectedValueOnce(new Error('page two failed'))
    await act(async () => {
      root.render(
        <Probe
          token="t"
          salonId="salon"
          change={{
            kind: 'working_hours.delete',
            working_hours_id: 'wh-1',
          }}
          impactLimit={1}
        />,
      )
      await flushPromises()
    })
    await act(async () => {
      latest?.loadMore()
      await flushPromises()
    })
    expect(latest?.error).toBe(null)
    expect(latest?.loadMoreError).toBeTruthy()
    expect(latest?.impacts.map((r) => r.booking_id)).toEqual(['b-1'])
  })

  it('does not reset acknowledgement on successful load more', async () => {
    mockedPreview
      .mockResolvedValueOnce(
        makeScheduleImpactPreviewResponse({
          counts: { total_impacted: 2, by_reason: {} },
          commit_policy: {
            allow_commit_with_impacts: true,
            requires_acknowledgement: true,
          },
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
              reasons: [],
            },
          ],
          pagination: {
            offset: 0,
            limit: 1,
            returned: 1,
            total_impacted: 2,
            has_more: true,
          },
        }),
      )
      .mockResolvedValueOnce(
        makeScheduleImpactPreviewResponse({
          counts: { total_impacted: 2, by_reason: {} },
          impacts: [
            {
              booking_id: 'b-2',
              status: 'confirmed',
              is_in_progress: false,
              starts_at: '2026-01-02T10:00:00+00:00',
              ends_at: '2026-01-02T11:00:00+00:00',
              staff_id: 's1',
              service_id: 'v1',
              customer_name: 'B',
              service_name: 'S',
              reasons: [],
            },
          ],
          pagination: {
            offset: 1,
            limit: 1,
            returned: 1,
            total_impacted: 2,
            has_more: false,
          },
        }),
      )
    await act(async () => {
      root.render(
        <Probe
          token="t"
          salonId="salon"
          change={{
            kind: 'working_hours.delete',
            working_hours_id: 'wh-1',
          }}
          impactLimit={1}
        />,
      )
      await flushPromises()
    })
    await act(async () => {
      latest?.setAcknowledgementChecked(true)
    })
    await act(async () => {
      latest?.loadMore()
      await flushPromises()
    })
    expect(latest?.acknowledgementChecked).toBe(true)
  })

  it('uses change from ref when changeKey is stable across rerenders', async () => {
    mockedPreview.mockResolvedValue(makeScheduleImpactPreviewResponse())
    const change = {
      kind: 'working_hours.delete' as const,
      working_hours_id: 'wh-1',
    }
    await act(async () => {
      root.render(<Probe token="t" salonId="salon" change={change} />)
      await flushPromises()
    })
    expect(mockedPreview).toHaveBeenCalledTimes(1)
    const newRef = { ...change }
    await act(async () => {
      root.render(<Probe token="t" salonId="salon" change={newRef} />)
      await flushPromises()
    })
    expect(mockedPreview).toHaveBeenCalledTimes(1)
  })
})

