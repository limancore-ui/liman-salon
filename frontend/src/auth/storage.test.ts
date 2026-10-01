import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  clearAdminAuthStorage,
  getStoredAccessToken,
  getStoredSalonIdHint,
  setStoredAccessToken,
  setStoredSalonIdHint,
} from './storage'

const memoryStore = new Map<string, string>()

beforeEach(() => {
  memoryStore.clear()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => memoryStore.get(key) ?? null,
    setItem: (key: string, value: string) => {
      memoryStore.set(key, value)
    },
    removeItem: (key: string) => {
      memoryStore.delete(key)
    },
    clear: () => {
      memoryStore.clear()
    },
  })
})

describe('clearAdminAuthStorage', () => {
  it('clears token and salon hint on logout', () => {
    setStoredAccessToken('token-value')
    setStoredSalonIdHint('salon-id')
    clearAdminAuthStorage()
    expect(getStoredAccessToken()).toBeNull()
    expect(getStoredSalonIdHint()).toBeNull()
  })
})
