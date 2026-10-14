import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from './errors'
import { createAdminStaff, patchAdminStaff } from './staff'

const salonId = 'salon-a'
const token = 'test-token'
const staffId = 'staff-1'

const staffRow = {
  id: staffId,
  display_name: 'Alex',
  title: null,
  bio: null,
  color_hex: '#AABBCC',
  is_bookable: true,
  is_active: true,
  sort_order: 0,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('createAdminStaff', () => {
  it('POSTs create contract to salon staff collection', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => staffRow,
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await createAdminStaff(token, salonId, {
      display_name: 'Alex',
      color_hex: '#AABBCC',
    })

    expect(result).toEqual(staffRow)
    expect(fetchMock).toHaveBeenCalledWith(`/api/v1/salons/${salonId}/staff`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        display_name: 'Alex',
        color_hex: '#AABBCC',
      }),
    })
  })

  it('throws ApiError with validation detail array on 422', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        statusText: 'Unprocessable Entity',
        json: async () => ({
          detail: [
            { type: 'string_too_long', loc: ['body', 'title'], msg: 'String should have at most 100 characters' },
          ],
        }),
      }),
    )

    await expect(
      createAdminStaff(token, salonId, { display_name: 'Alex', title: 'x'.repeat(101) }),
    ).rejects.toEqual(
      expect.objectContaining({
        status: 422,
        message: 'String should have at most 100 characters',
      }),
    )
  })

  it('throws ApiError with backend detail on failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        statusText: 'Unprocessable Entity',
        json: async () => ({ detail: 'display_name must not be blank' }),
      }),
    )

    await expect(
      createAdminStaff(token, salonId, { display_name: '   ' }),
    ).rejects.toEqual(
      expect.objectContaining({
        status: 422,
        message: 'display_name must not be blank',
      }),
    )
  })

  it('throws ApiError with code on 403 forbidden', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        statusText: 'Forbidden',
        json: async () => ({ detail: 'Forbidden', code: 'forbidden' }),
      }),
    )

    const err = await createAdminStaff(token, salonId, {
      display_name: 'Alex',
    }).catch((e: unknown) => e)

    expect(err).toBeInstanceOf(ApiError)
    expect(err).toMatchObject({ status: 403, code: 'forbidden' })
  })
})

describe('patchAdminStaff', () => {
  it('PATCHes partial update to staff resource', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ...staffRow, is_active: false }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await patchAdminStaff(token, salonId, staffId, { is_active: false })

    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/salons/${salonId}/staff/${staffId}`,
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

  it('PATCHes editable staff fields with partial body', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        ...staffRow,
        display_name: 'Jordan',
        title: 'Stylist',
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await patchAdminStaff(token, salonId, staffId, {
      display_name: 'Jordan',
      title: 'Stylist',
    })

    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/salons/${salonId}/staff/${staffId}`,
      {
        method: 'PATCH',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ display_name: 'Jordan', title: 'Stylist' }),
      },
    )
  })

  it('throws ApiError on API failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        json: async () => ({ detail: 'Staff not found' }),
      }),
    )

    await expect(
      patchAdminStaff(token, salonId, staffId, { display_name: 'Updated' }),
    ).rejects.toMatchObject({ status: 404, message: 'Staff not found' })
  })
})
