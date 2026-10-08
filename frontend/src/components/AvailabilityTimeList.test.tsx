import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { AvailabilityTimeList } from './AvailabilityTimeList'

describe('AvailabilityTimeList', () => {
  it('renders multiple discrete start buttons', () => {
    const html = renderToStaticMarkup(
      <AvailabilityTimeList
        state={{
          status: 'success',
          slots: [
            {
              staff_id: 'staff-a',
              service_start: '2026-07-10T10:00:00.000Z',
              service_end: '2026-07-10T11:00:00.000Z',
            },
            {
              staff_id: 'staff-a',
              service_start: '2026-07-10T10:30:00.000Z',
              service_end: '2026-07-10T11:30:00.000Z',
            },
          ],
        }}
        selectedSlot={null}
        timeZone="UTC"
        onSelectSlot={() => {}}
      />,
    )
    expect(html.match(/time-slot/g)?.length).toBe(2)
  })

  it('renders empty state when no slots', () => {
    const html = renderToStaticMarkup(
      <AvailabilityTimeList
        state={{ status: 'success', slots: [] }}
        selectedSlot={null}
        timeZone="UTC"
        onSelectSlot={() => {}}
      />,
    )
    expect(html).toContain('time-list__empty')
  })
})
