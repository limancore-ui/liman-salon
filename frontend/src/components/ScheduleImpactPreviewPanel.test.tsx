import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { ScheduleImpactPreviewView } from './ScheduleImpactPreviewPanel'
import { makeScheduleImpactPreviewResponse } from './scheduleImpactPreviewFixtures'

describe('ScheduleImpactPreviewView', () => {
  it('renders loading state', () => {
    const html = renderToStaticMarkup(
      <ScheduleImpactPreviewView
        loading
        loadingMore={false}
        error={null}
        loadMoreError={null}
        response={null}
        impacts={[]}
        acknowledgementChecked={false}
        onAcknowledgementChange={() => {}}
        confirmDisabled
        canLoadMore={false}
        onRetry={() => {}}
        onLoadMore={() => {}}
        onCancel={() => {}}
        onConfirm={() => {}}
        confirmLabel="Продолжить"
      />,
    )
    expect(html).toContain('Загрузка влияния…')
  })

  it('renders empty result when total_impacted is zero', () => {
    const response = makeScheduleImpactPreviewResponse()
    const html = renderToStaticMarkup(
      <ScheduleImpactPreviewView
        loading={false}
        loadingMore={false}
        error={null}
        loadMoreError={null}
        response={response}
        impacts={[]}
        acknowledgementChecked={false}
        onAcknowledgementChange={() => {}}
        confirmDisabled={false}
        canLoadMore={false}
        onRetry={() => {}}
        onLoadMore={() => {}}
        onCancel={() => {}}
        onConfirm={() => {}}
        confirmLabel="Продолжить"
      />,
    )
    expect(html).toContain('В горизонте просмотра это изменение не затронет записи.')
    expect(html).toContain('0')
  })

  it('renders populated impacts with Russian reasons and status', () => {
    const response = makeScheduleImpactPreviewResponse({
      counts: { total_impacted: 1, by_reason: { outside_availability: 1 } },
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
    })
    const html = renderToStaticMarkup(
      <ScheduleImpactPreviewView
        loading={false}
        loadingMore={false}
        error={null}
        loadMoreError={null}
        response={response}
        impacts={[
          {
            booking_id: 'b-1',
            status: 'confirmed',
            is_in_progress: false,
            starts_at: '2026-02-01T10:00:00+00:00',
            ends_at: '2026-02-01T11:00:00+00:00',
            staff_id: 'staff-1',
            service_id: 'svc-1',
            customer_name: 'Alex Client',
            service_name: 'Haircut',
            reasons: ['outside_availability'],
          },
        ]}
        acknowledgementChecked={false}
        onAcknowledgementChange={() => {}}
        confirmDisabled
        canLoadMore={false}
        onRetry={() => {}}
        onLoadMore={() => {}}
        onCancel={() => {}}
        onConfirm={() => {}}
        confirmLabel="Продолжить"
      />,
    )
    expect(html).toContain('Alex Client')
    expect(html).toContain('Haircut')
    expect(html).toContain('Вне доступного времени или в заблокированном интервале')
    expect(html).toContain('Подтверждена')
    expect(html).toContain('Я понимаю, что может быть затронуто записей:')
    expect(html).toContain('может быть затронута этим изменением.')
  })

  it('renders API error with retry', () => {
    const html = renderToStaticMarkup(
      <ScheduleImpactPreviewView
        loading={false}
        loadingMore={false}
        error="Forbidden"
        loadMoreError={null}
        response={null}
        impacts={[]}
        acknowledgementChecked={false}
        onAcknowledgementChange={() => {}}
        confirmDisabled
        canLoadMore={false}
        onRetry={() => {}}
        onLoadMore={() => {}}
        onCancel={() => {}}
        onConfirm={() => {}}
        confirmLabel="Продолжить"
      />,
    )
    expect(html).toContain('Forbidden')
    expect(html).toContain('Повторить просмотр')
  })

  it('shows load more when canLoadMore', () => {
    const response = makeScheduleImpactPreviewResponse({
      counts: { total_impacted: 2, by_reason: {} },
      pagination: {
        offset: 0,
        limit: 1,
        returned: 1,
        total_impacted: 2,
        has_more: true,
      },
    })
    const html = renderToStaticMarkup(
      <ScheduleImpactPreviewView
        loading={false}
        loadingMore={false}
        error={null}
        loadMoreError={null}
        response={response}
        impacts={[
          {
            booking_id: 'b-1',
            status: 'pending',
            is_in_progress: false,
            starts_at: '2026-02-01T10:00:00+00:00',
            ends_at: '2026-02-01T11:00:00+00:00',
            staff_id: 'staff-1',
            service_id: 'svc-1',
            customer_name: 'A',
            service_name: 'S',
            reasons: [],
          },
        ]}
        acknowledgementChecked={false}
        onAcknowledgementChange={() => {}}
        confirmDisabled={false}
        canLoadMore
        onRetry={() => {}}
        onLoadMore={() => {}}
        onCancel={() => {}}
        onConfirm={() => {}}
        confirmLabel="Продолжить"
      />,
    )
    expect(html).toContain('Загрузить ещё записи')
    expect(html).toContain('Показано')
    expect(html).toContain('из')
  })

  it('renders load more error without hiding the list', () => {
    const response = makeScheduleImpactPreviewResponse({
      counts: { total_impacted: 2, by_reason: {} },
      pagination: {
        offset: 0,
        limit: 1,
        returned: 1,
        total_impacted: 2,
        has_more: true,
      },
    })
    const html = renderToStaticMarkup(
      <ScheduleImpactPreviewView
        loading={false}
        loadingMore={false}
        error={null}
        loadMoreError="Could not load more"
        response={response}
        impacts={[
          {
            booking_id: 'b-1',
            status: 'pending',
            is_in_progress: false,
            starts_at: '2026-02-01T10:00:00+00:00',
            ends_at: '2026-02-01T11:00:00+00:00',
            staff_id: 'staff-1',
            service_id: 'svc-1',
            customer_name: 'A',
            service_name: 'S',
            reasons: [],
          },
        ]}
        acknowledgementChecked={false}
        onAcknowledgementChange={() => {}}
        confirmDisabled={false}
        canLoadMore
        onRetry={() => {}}
        onLoadMore={() => {}}
        onCancel={() => {}}
        onConfirm={() => {}}
        confirmLabel="Продолжить"
      />,
    )
    expect(html).toContain('Could not load more')
    expect(html).toContain('A')
    expect(html).toContain('Показано')
  })

  it('disables confirm when confirmDisabled', () => {
    const response = makeScheduleImpactPreviewResponse()
    const html = renderToStaticMarkup(
      <ScheduleImpactPreviewView
        loading={false}
        loadingMore={false}
        error={null}
        loadMoreError={null}
        response={response}
        impacts={[]}
        acknowledgementChecked={false}
        onAcknowledgementChange={() => {}}
        confirmDisabled
        canLoadMore={false}
        onRetry={() => {}}
        onLoadMore={() => {}}
        onCancel={() => {}}
        onConfirm={() => {}}
        confirmLabel="Продолжить"
      />,
    )
    expect(html).toContain('disabled=""')
  })
})
