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
import type { AdminSession, PendingWorkspaceAuth } from '../types/auth'
import { clearAdminAuthStorage, getStoredAccessToken } from './storage'
import {
  completeWorkspaceSelection,
  establishAdminSession,
  loadAdminSession,
  NoSalonAccessError,
  switchAdminSalon,
} from './session'

export type AuthStatus =
  | 'loading'
  | 'authenticated'
  | 'unauthenticated'
  | 'no_salon_access'
  | 'workspace_picker'

type AuthContextValue = {
  status: AuthStatus
  session: AdminSession | null
  pendingWorkspace: PendingWorkspaceAuth | null
  login: (email: string, password: string) => Promise<void>
  selectWorkspace: (salonId: string) => Promise<void>
  switchWorkspace: (salonId: string) => Promise<void>
  logout: () => void
  clearAuthAndRedirect: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

type AuthProviderProps = {
  children: ReactNode
}

function applyLoadResult(
  result: Awaited<ReturnType<typeof loadAdminSession>>,
  handlers: {
    setSession: (session: AdminSession | null) => void
    setPendingWorkspace: (pending: PendingWorkspaceAuth | null) => void
    setStatus: (status: AuthStatus) => void
  },
): void {
  if (result.kind === 'session') {
    handlers.setSession(result.session)
    handlers.setPendingWorkspace(null)
    handlers.setStatus('authenticated')
    return
  }
  handlers.setSession(null)
  handlers.setPendingWorkspace(result.pending)
  handlers.setStatus(
    result.kind === 'no_access' ? 'no_salon_access' : 'workspace_picker',
  )
}

export function AuthProvider({ children }: AuthProviderProps) {
  const navigate = useNavigate()
  const [status, setStatus] = useState<AuthStatus>('loading')
  const [session, setSession] = useState<AdminSession | null>(null)
  const [pendingWorkspace, setPendingWorkspace] =
    useState<PendingWorkspaceAuth | null>(null)

  const clearAuthAndRedirect = useCallback(() => {
    clearAdminAuthStorage()
    setSession(null)
    setPendingWorkspace(null)
    setStatus('unauthenticated')
    navigate('/admin/login', { replace: true })
  }, [navigate])

  const logout = useCallback(() => {
    clearAdminAuthStorage()
    setSession(null)
    setPendingWorkspace(null)
    setStatus('unauthenticated')
    navigate('/admin/login', { replace: true })
  }, [navigate])

  const bootstrap = useCallback(async () => {
    const token = getStoredAccessToken()
    if (!token) {
      setSession(null)
      setPendingWorkspace(null)
      setStatus('unauthenticated')
      return
    }
    setStatus('loading')
    try {
      const result = await loadAdminSession(token)
      applyLoadResult(result, {
        setSession,
        setPendingWorkspace,
        setStatus,
      })
    } catch (error) {
      if (isUnauthorizedError(error)) {
        clearAuthAndRedirect()
        return
      }
      clearAdminAuthStorage()
      setSession(null)
      setPendingWorkspace(null)
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

  const login = useCallback(async (email: string, password: string) => {
    const { access_token: token } = await loginWithPassword(email, password)
    try {
      const result = await establishAdminSession(token)
      applyLoadResult(result, {
        setSession,
        setPendingWorkspace,
        setStatus,
      })
      if (result.kind === 'no_access') {
        throw new NoSalonAccessError(
          'Your account is not linked to any active salon workspace.',
        )
      }
    } catch (error) {
      if (error instanceof NoSalonAccessError) {
        throw error
      }
      if (isUnauthorizedError(error)) {
        clearAdminAuthStorage()
        setSession(null)
        setPendingWorkspace(null)
        setStatus('unauthenticated')
        throw error
      }
      clearAdminAuthStorage()
      setSession(null)
      setPendingWorkspace(null)
      setStatus('unauthenticated')
      throw error
    }
  }, [])

  const selectWorkspace = useCallback(async (salonId: string) => {
    if (!pendingWorkspace) {
      throw new Error('No workspace selection is pending.')
    }
    setStatus('loading')
    try {
      const nextSession = await completeWorkspaceSelection(
        pendingWorkspace,
        salonId,
      )
      setSession(nextSession)
      setPendingWorkspace(null)
      setStatus('authenticated')
    } catch (error) {
      if (isUnauthorizedError(error)) {
        clearAuthAndRedirect()
        return
      }
      setStatus('workspace_picker')
      throw error
    }
  }, [pendingWorkspace, clearAuthAndRedirect])

  const switchWorkspace = useCallback(
    async (salonId: string) => {
      if (!session) {
        return
      }
      setStatus('loading')
      try {
        const nextSession = await switchAdminSalon(session, salonId)
        setSession(nextSession)
        setStatus('authenticated')
      } catch (error) {
        if (isUnauthorizedError(error)) {
          clearAuthAndRedirect()
          return
        }
        setStatus('authenticated')
        throw error
      }
    },
    [session, clearAuthAndRedirect],
  )

  const value = useMemo(
    (): AuthContextValue => ({
      status,
      session,
      pendingWorkspace,
      login,
      selectWorkspace,
      switchWorkspace,
      logout,
      clearAuthAndRedirect,
    }),
    [
      status,
      session,
      pendingWorkspace,
      login,
      selectWorkspace,
      switchWorkspace,
      logout,
      clearAuthAndRedirect,
    ],
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
