import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from './errors'
import {
  attachAdminStaffToService,
  createAdminService,
  detachAdminStaffFromService,
  fetchAdminStaffForService,
  patchAdminService,
} from './services'

const salonId = 'salon-a'
const token = 'test-token'
const serviceId = 'svc-1'
const staffId = 'staff-1'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('createAdminService', () => {
  it('POSTs create contract to salon services collection', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: serviceId, name: 'Cut' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await createAdminService(token, salonId, {
      name: 'Cut',
      duration_minutes: 45,
      price_cents: 2500,
    })

    expect(fetchMock).toHaveBeenCalledWith(`/api/v1/salons/${salonId}/services`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name: 'Cut',
        duration_minutes: 45,
        price_cents: 2500,
      }),
    })
  })

  it('throws ApiError with backend detail on failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        statusText: 'Unprocessable Entity',
        json: async () => ({ detail: 'duration_minutes must be positive' }),
      }),
    )

    await expect(
      createAdminService(token, salonId, { name: 'Cut', duration_minutes: 0 }),
    ).rejects.toEqual(
      expect.objectContaining({
        status: 422,
        message: 'duration_minutes must be positive',
      }),
    )
  })
})

describe('patchAdminService', () => {
  it('PATCHes partial update to service resource', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: serviceId, is_active: false }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await patchAdminService(token, salonId, serviceId, { is_active: false })

    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/salons/${salonId}/services/${serviceId}`,
      {
        method: 'PATCH',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ is_active: false }),
      },
    )
  })

  it('PATCHes editable service fields with partial body', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: serviceId, name: 'Trim', price_cents: 3000 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await patchAdminService(token, salonId, serviceId, {
      name: 'Trim',
      price_cents: 3000,
    })

    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/salons/${salonId}/services/${serviceId}`,
      {
        method: 'PATCH',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name: 'Trim', price_cents: 3000 }),
      },
    )
  })

  it('PATCHes is_active toggle without other fields', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: serviceId, is_active: true }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await patchAdminService(token, salonId, serviceId, { is_active: true })

    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/salons/${salonId}/services/${serviceId}`,
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ is_active: true }),
      }),
    )
  })

  it('throws ApiError on 403 forbidden', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        statusText: 'Forbidden',
        json: async () => ({ detail: 'Forbidden', code: 'forbidden' }),
      }),
    )

    const err = await patchAdminService(token, salonId, serviceId, {
      name: 'Updated',
    }).catch((e: unknown) => e)

    expect(err).toBeInstanceOf(ApiError)
    expect(err).toMatchObject({ status: 403, code: 'forbidden' })
  })
})

describe('fetchAdminStaffForService', () => {
  it('GETs staff list for a service', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ id: staffId, display_name: 'Alex' }],
    })
    vi.stubGlobal('fetch', fetchMock)

    const rows = await fetchAdminStaffForService(token, salonId, serviceId)

    expect(rows).toHaveLength(1)
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/salons/${salonId}/services/${serviceId}/staff`,
      {
        headers: { Authorization: `Bearer ${token}` },
      },
    )
  })
})

describe('attachAdminStaffToService', () => {
  it('PUTs staff assignment URL without body', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: staffId, display_name: 'Alex' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await attachAdminStaffToService(token, salonId, serviceId, staffId)

    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/salons/${salonId}/services/${serviceId}/staff/${staffId}`,
      {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}` },
      },
    )
  })
})

describe('detachAdminStaffFromService', () => {
  it('DELETEs staff assignment URL', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
    })
    vi.stubGlobal('fetch', fetchMock)

    await detachAdminStaffFromService(token, salonId, serviceId, staffId)

    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/salons/${salonId}/services/${serviceId}/staff/${staffId}`,
      {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      },
    )
  })

  it('throws ApiError when detach fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        json: async () => ({ detail: 'Staff not linked to service' }),
      }),
    )

    await expect(
      detachAdminStaffFromService(token, salonId, serviceId, staffId),
    ).rejects.toMatchObject({ status: 404, message: 'Staff not linked to service' })
  })
})
