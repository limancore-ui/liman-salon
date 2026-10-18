import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from './errors'
import {
  createAdminShowcaseItem,
  deleteAdminShowcaseItem,
  fetchAdminShowcaseItems,
  patchAdminShowcaseItem,
  publishAdminShowcaseItem,
  unpublishAdminShowcaseItem,
} from './adminShowcase'
import type { AdminShowcaseItem } from '../types/adminShowcase'

const item: AdminShowcaseItem = {
  id: 'item-1',
  salon_id: 'salon-1',
  category: 'work',
  title: 'Hair style',
  description: null,
  price_cents: null,
  media_asset_id: 'media-1',
  sort_order: 0,
  is_published: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const fetchMock = vi.fn<typeof fetch>()

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 403 ? 'Forbidden' : 'Error',
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response
}

describe('admin Showcase API', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('loads tenant items with encoded salon id and pagination', async () => {
    fetchMock.mockResolvedValue(response([item]))

    await expect(
      fetchAdminShowcaseItems('token', 'salon/one', { limit: 25, offset: 50 }),
    ).resolves.toEqual([item])

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/salons/salon%2Fone/showcase/items?limit=25&offset=50',
      { headers: { Authorization: 'Bearer token' } },
    )
  })

  it('creates with only backend-supported fields and does not send protected tenant or publication fields', async () => {
    fetchMock.mockResolvedValue(response(item))
    const body = {
      category: 'work' as const,
      title: 'Hair style',
      media_asset_id: 'media-1',
      description: null,
      price_cents: null,
      sort_order: 3,
    }

    await createAdminShowcaseItem('token', 'salon-1', body)

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/salons/salon-1/showcase/items')
    expect(init?.method).toBe('POST')
    expect(init?.headers).toEqual({
      Authorization: 'Bearer token',
      'Content-Type': 'application/json',
    })
    const sent = JSON.parse(String(init?.body)) as Record<string, unknown>
    expect(sent).toEqual(body)
    expect(sent).not.toHaveProperty('salon_id')
    expect(sent).not.toHaveProperty('is_published')
  })

  it('uses the contract methods and paths for patch, publish, unpublish, and delete', async () => {
    fetchMock
      .mockResolvedValueOnce(response(item))
      .mockResolvedValueOnce(response(item))
      .mockResolvedValueOnce(response(item))
      .mockResolvedValueOnce({ ok: true, status: 204 } as Response)

    await patchAdminShowcaseItem('token', 'salon-1', 'item-1', { title: 'Updated' })
    await publishAdminShowcaseItem('token', 'salon-1', 'item-1')
    await unpublishAdminShowcaseItem('token', 'salon-1', 'item-1')
    await deleteAdminShowcaseItem('token', 'salon-1', 'item-1')

    expect(fetchMock.mock.calls.map(([url, init]) => [url, init?.method])).toEqual([
      ['/api/v1/salons/salon-1/showcase/items/item-1', 'PATCH'],
      ['/api/v1/salons/salon-1/showcase/items/item-1/publish', 'PATCH'],
      ['/api/v1/salons/salon-1/showcase/items/item-1/unpublish', 'PATCH'],
      ['/api/v1/salons/salon-1/showcase/items/item-1', 'DELETE'],
    ])
  })

  it('normalizes forbidden responses as ApiError', async () => {
    fetchMock.mockResolvedValue(response({ detail: 'forbidden', code: 'forbidden' }, 403))

    await expect(
      fetchAdminShowcaseItems('token', 'salon-1'),
    ).rejects.toMatchObject({
      status: 403,
      code: 'forbidden',
      name: 'ApiError',
    } satisfies Partial<ApiError>)
  })
})
