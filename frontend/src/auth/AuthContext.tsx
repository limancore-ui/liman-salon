import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { useNavigate } from 'react-router-dom'
import {
  fetchCurrentUser,
  isUnauthorizedError,
  loginWithPassword,
} from '../api/auth'
import type { AdminSession } from '../types/auth'
import { clearAdminAuthStorage, getStoredAccessToken } from './storage'
import {
  establishAdminSession,
  loadAdminSession,
  SalonContextResolutionError,
} from './session'

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated'

type AuthContextValue = {
  status: AuthStatus
  session: AdminSession | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  clearAuthAndRedirect: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

type AuthProviderProps = {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const navigate = useNavigate()
  const [status, setStatus] = useState<AuthStatus>('loading')
  const [session, setSession] = useState<AdminSession | null>(null)

  const clearAuthAndRedirect = useCallback(() => {
    clearAdminAuthStorage()
    setSession(null)
    setStatus('unauthenticated')
    navigate('/admin/login', { replace: true })
  }, [navigate])

  const logout = useCallback(() => {
    clearAdminAuthStorage()
    setSession(null)
    setStatus('unauthenticated')
    navigate('/admin/login', { replace: true })
  }, [navigate])

  const bootstrap = useCallback(async () => {
    const token = getStoredAccessToken()
    if (!token) {
      setSession(null)
      setStatus('unauthenticated')
      return
    }
    setStatus('loading')
    try {
      const loaded = await loadAdminSession(token)
      setSession(loaded)
      setStatus('authenticated')
    } catch (error) {
      if (isUnauthorizedError(error)) {
        clearAuthAndRedirect()
        return
      }
      clearAdminAuthStorage()
      setSession(null)
      setStatus('unauthenticated')
    }
  }, [clearAuthAndRedirect])

  useEffect(() => {
    void bootstrap()
  }, [bootstrap])

  useEffect(() => {
    if (!session) {
      return
    }
    const token = session.token
    const revalidate = () => {
      if (document.visibilityState !== 'visible') {
        return
      }
      void fetchCurrentUser(token).catch((error: unknown) => {
        if (isUnauthorizedError(error)) {
          clearAuthAndRedirect()
        }
      })
    }
    document.addEventListener('visibilitychange', revalidate)
    return () => document.removeEventListener('visibilitychange', revalidate)
  }, [session, clearAuthAndRedirect])

  const login = useCallback(
    async (email: string, password: string) => {
      const { access_token: token } = await loginWithPassword(email, password)
      try {
        const nextSession = await establishAdminSession(token)
        setSession(nextSession)
        setStatus('authenticated')
      } catch (error) {
        clearAdminAuthStorage()
        setSession(null)
        setStatus('unauthenticated')
        if (error instanceof SalonContextResolutionError) {
          throw error
        }
        if (isUnauthorizedError(error)) {
          throw error
        }
        throw error
      }
    },
    [],
  )

  const value = useMemo(
    (): AuthContextValue => ({
      status,
      session,
      login,
      logout,
      clearAuthAndRedirect,
    }),
    [status, session, login, logout, clearAuthAndRedirect],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (ctx === null) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return ctx
}
