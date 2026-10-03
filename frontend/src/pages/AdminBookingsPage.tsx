import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AdminLayout } from '../components/AdminLayout'
import { useAuth } from '../auth/AuthContext'
import {
  cancelAdminBooking,
  completeAdminVisit,
  confirmAdminBooking,
  createAdminBooking,
  fetchAdminBookings,
  markAdminNoShow,
  rescheduleAdminBooking,
  startAdminVisit,
} from '../api/bookings'
import { fetchAdminCustomers } from '../api/customers'
import { fetchAdminServices, fetchAdminStaffForService } from '../api/services'
import { fetchAdminStaff } from '../api/staff'
import { ApiError } from '../api/errors'
import { isUnauthorizedError } from '../api/auth'
import type { AdminBookingCreateStatus, BookingListItem } from '../types/bookings'
import type { CustomerListItem } from '../types/customers'
import type { ServiceListItem } from '../types/services'
import type { StaffListItem } from '../types/staff'
import {
  isAdminBookingSlotConflictError,
  mapAdminBookingActionError,
  mapAdminBookingCreateError,
} from '../utils/mapAdminBookingActionError'
import {
  formatBookingDateTime,
  formatDashboardPrice,
} from '../utils/adminSalonFormat'
import {
  isoToSalonLocalDatetimeLocal,
  salonLocalDateRangeToUtcIso,
  salonLocalDateTimeToIso,
} from '../utils/adminBookingTime'
import { parseAdminBookingsFilterParams } from '../utils/adminBookingsFilterParams'

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'pending', label: 'Pending' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
  { value: 'no_show', label: 'No show' },
  { value: 'expired', label: 'Expired' },
] as const

const CREATE_STATUS_OPTIONS = [
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'pending', label: 'Pending' },
] as const satisfies ReadonlyArray<{
  value: AdminBookingCreateStatus
  label: string
}>

type BookingActionMode = 'cancel' | 'reschedule'

function canManageBookings(role: string | undefined): boolean {
  return role === 'owner' || role === 'admin'
}

function isActionableBookingStatus(status: string): boolean {
  return status === 'pending' || status === 'confirmed'
}

function hasVisitLifecycleActions(status: string): boolean {
  return status === 'confirmed' || status === 'in_progress'
}

function resolveStaffIdForBooking(
  staffList: StaffListItem[],
  staffName: string,
): string {
  const match = staffList.find((row) => row.display_name === staffName)
  if (match) {
    return match.id
  }
  const bookable = staffList.find((row) => row.is_bookable && row.is_active)
  return bookable?.id ?? staffList[0]?.id ?? ''
}

export function AdminBookingsPage() {
  const { session, clearAuthAndRedirect } = useAuth()
  const [searchParams] = useSearchParams()
  const initialFilters = parseAdminBookingsFilterParams(searchParams)
  const [items, setItems] = useState<BookingListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dateFrom, setDateFrom] = useState(initialFilters.dateFrom)
  const [dateTo, setDateTo] = useState(initialFilters.dateTo)
  const [status, setStatus] = useState(initialFilters.status)

  const [staffList, setStaffList] = useState<StaffListItem[]>([])
  const [staffLoading, setStaffLoading] = useState(false)

  const [actionBooking, setActionBooking] = useState<BookingListItem | null>(null)
  const [actionMode, setActionMode] = useState<BookingActionMode | null>(null)
  const [cancelReason, setCancelReason] = useState('')
  const [rescheduleStaffId, setRescheduleStaffId] = useState('')
  const [rescheduleStartLocal, setRescheduleStartLocal] = useState('')
  const [actionSubmitting, setActionSubmitting] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const [createOpen, setCreateOpen] = useState(false)
  const [createCustomerSearch, setCreateCustomerSearch] = useState('')
  const [createCustomers, setCreateCustomers] = useState<CustomerListItem[]>([])
  const [createCustomersLoading, setCreateCustomersLoading] = useState(false)
  const [createCustomerId, setCreateCustomerId] = useState('')
  const [createServices, setCreateServices] = useState<ServiceListItem[]>([])
  const [createServicesLoading, setCreateServicesLoading] = useState(false)
  const [createServiceId, setCreateServiceId] = useState('')
  const [createServiceStaffIds, setCreateServiceStaffIds] = useState<string[]>([])
  const [createServiceStaffLoading, setCreateServiceStaffLoading] = useState(false)
  const [createStaffId, setCreateStaffId] = useState('')
  const [createStartLocal, setCreateStartLocal] = useState('')
  const [createStatus, setCreateStatus] = useState<AdminBookingCreateStatus>('confirmed')
  const [createSubmitting, setCreateSubmitting] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const manage = canManageBookings(session?.salon.role)
  const salonTimeZone = session?.salon.timezone
  const salonTimeZoneForInput = salonTimeZone ?? 'UTC'
  const salonCurrencyCode = session?.salon.currency_code ?? undefined

  const clearAction = useCallback(() => {
    setActionBooking(null)
    setActionMode(null)
    setCancelReason('')
    setRescheduleStaffId('')
    setRescheduleStartLocal('')
    setActionError(null)
  }, [])

  const clearCreate = useCallback(() => {
    setCreateOpen(false)
    setCreateCustomerSearch('')
    setCreateCustomers([])
    setCreateCustomerId('')
    setCreateServiceId('')
    setCreateServiceStaffIds([])
    setCreateStaffId('')
    setCreateStartLocal('')
    setCreateStatus('confirmed')
    setCreateError(null)
  }, [])

  const startCreate = useCallback(() => {
    clearAction()
    setCreateOpen(true)
    setCreateError(null)
    setCreateCustomerSearch('')
    setCreateCustomers([])
    setCreateCustomerId('')
    setCreateServiceId('')
    setCreateServiceStaffIds([])
    setCreateStaffId('')
    setCreateStartLocal('')
    setCreateStatus('confirmed')
  }, [clearAction])

  const load = useCallback(async () => {
    if (!session) {
      return
    }
    setLoading(true)
    setError(null)
    try {
      const range = salonLocalDateRangeToUtcIso(dateFrom, dateTo, salonTimeZoneForInput)
      const rows = await fetchAdminBookings(session.token, session.salon.salon_id, {
        ...range,
        status: status || undefined,
        limit: 100,
      })
      setItems(rows)
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError('Could not load bookings.')
      }
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [
    session,
    dateFrom,
    dateTo,
    status,
    salonTimeZoneForInput,
    clearAuthAndRedirect,
  ])

  useEffect(() => {
    const parsed = parseAdminBookingsFilterParams(searchParams)
    setDateFrom(parsed.dateFrom)
    setDateTo(parsed.dateTo)
    setStatus(parsed.status)
  }, [searchParams])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (!session || !manage) {
      setStaffList([])
      return
    }

    let cancelled = false
    setStaffLoading(true)
    fetchAdminStaff(session.token, session.salon.salon_id, {
      active_only: true,
      bookable_only: true,
    })
      .then((rows) => {
        if (!cancelled) {
          setStaffList(rows)
        }
      })
      .catch((err: unknown) => {
        if (cancelled) {
          return
        }
        if (isUnauthorizedError(err)) {
          clearAuthAndRedirect()
          return
        }
        setStaffList([])
      })
      .finally(() => {
        if (!cancelled) {
          setStaffLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [session, manage, clearAuthAndRedirect])

  useEffect(() => {
    if (!session || !manage || !createOpen) {
      setCreateServices([])
      return
    }

    let cancelled = false
    setCreateServicesLoading(true)
    fetchAdminServices(session.token, session.salon.salon_id, { active_only: true })
      .then((rows) => {
        if (!cancelled) {
          setCreateServices(rows)
        }
      })
      .catch((err: unknown) => {
        if (cancelled) {
          return
        }
        if (isUnauthorizedError(err)) {
          clearAuthAndRedirect()
          return
        }
        setCreateServices([])
        setCreateError('Could not load services.')
      })
      .finally(() => {
        if (!cancelled) {
          setCreateServicesLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [session, manage, createOpen, clearAuthAndRedirect])

  useEffect(() => {
    if (!session || !manage || !createOpen || !createServiceId) {
      setCreateServiceStaffIds([])
      setCreateStaffId('')
      return
    }

    let cancelled = false
    setCreateServiceStaffLoading(true)
    fetchAdminStaffForService(session.token, session.salon.salon_id, createServiceId)
      .then((rows) => {
        if (!cancelled) {
          setCreateServiceStaffIds(rows.map((row) => row.id))
        }
      })
      .catch((err: unknown) => {
        if (cancelled) {
          return
        }
        if (isUnauthorizedError(err)) {
          clearAuthAndRedirect()
          return
        }
        setCreateServiceStaffIds([])
        setCreateStaffId('')
        setCreateError('Could not load staff for this service.')
      })
      .finally(() => {
        if (!cancelled) {
          setCreateServiceStaffLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [session, manage, createOpen, createServiceId, clearAuthAndRedirect])

  const createStaffList = staffList.filter((row) => createServiceStaffIds.includes(row.id))

  useEffect(() => {
    if (!createOpen || !createServiceId) {
      return
    }
    setCreateStaffId((current) =>
      createStaffList.some((row) => row.id === current)
        ? current
        : (createStaffList[0]?.id ?? ''),
    )
  }, [createOpen, createServiceId, createStaffList])

  const searchCreateCustomers = useCallback(async () => {
    if (!session || !createOpen) {
      return
    }
    setCreateCustomersLoading(true)
    setCreateError(null)
    try {
      const trimmed = createCustomerSearch.trim()
      const rows = await fetchAdminCustomers(session.token, session.salon.salon_id, {
        q: trimmed === '' ? undefined : trimmed,
        limit: 50,
      })
      setCreateCustomers(rows)
      setCreateCustomerId((current) =>
        rows.some((row) => row.id === current) ? current : (rows[0]?.id ?? ''),
      )
    } catch (err: unknown) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      setCreateCustomers([])
      setCreateCustomerId('')
      setCreateError('Could not search customers.')
    } finally {
      setCreateCustomersLoading(false)
    }
  }, [session, createOpen, createCustomerSearch, clearAuthAndRedirect])

  const startCancel = useCallback((row: BookingListItem) => {
    clearCreate()
    setActionError(null)
    setActionBooking(row)
    setActionMode('cancel')
    setCancelReason('')
  }, [clearCreate])

  const startReschedule = useCallback(
    (row: BookingListItem) => {
      clearCreate()
      setActionError(null)
      setActionBooking(row)
      setActionMode('reschedule')
      setRescheduleStaffId(resolveStaffIdForBooking(staffList, row.staff_name))
      setRescheduleStartLocal(isoToSalonLocalDatetimeLocal(row.starts_at, salonTimeZoneForInput))
    },
    [clearCreate, staffList, salonTimeZoneForInput],
  )

  const handleConfirmCreate = useCallback(
    async (event: FormEvent) => {
      event.preventDefault()
      if (!session || !createOpen || createSubmitting) {
        return
      }
      if (!createCustomerId) {
        setCreateError('Select a customer.')
        return
      }
      if (!createServiceId) {
        setCreateError('Select a service.')
        return
      }
      if (!createStaffId) {
        setCreateError('Select a staff member.')
        return
      }
      if (!createStartLocal) {
        setCreateError('Choose a service start time.')
        return
      }

      setCreateSubmitting(true)
      setCreateError(null)
      try {
        await createAdminBooking(session.token, session.salon.salon_id, {
          customer_id: createCustomerId,
          staff_id: createStaffId,
          service_id: createServiceId,
          requested_service_start: salonLocalDateTimeToIso(
            createStartLocal,
            salonTimeZoneForInput,
          ),
          source: 'admin',
          status: createStatus,
        })
        clearCreate()
        await load()
      } catch (err: unknown) {
        if (isUnauthorizedError(err)) {
          clearAuthAndRedirect()
          return
        }
        setCreateError(mapAdminBookingCreateError(err))
        if (isAdminBookingSlotConflictError(err)) {
          setCreateStartLocal('')
        }
      } finally {
        setCreateSubmitting(false)
      }
    },
    [
      session,
      createOpen,
      createSubmitting,
      createCustomerId,
      createServiceId,
      createStaffId,
      createStartLocal,
      createStatus,
      salonTimeZoneForInput,
      clearCreate,
      load,
      clearAuthAndRedirect,
    ],
  )

  const handleConfirmPending = useCallback(
    async (row: BookingListItem) => {
      if (!session || actionSubmitting) {
        return
      }
      setActionSubmitting(true)
      setActionError(null)
      try {
        await confirmAdminBooking(session.token, session.salon.salon_id, row.id)
        clearAction()
        await load()
      } catch (err: unknown) {
        if (isUnauthorizedError(err)) {
          clearAuthAndRedirect()
          return
        }
        setActionError(mapAdminBookingActionError(err))
      } finally {
        setActionSubmitting(false)
      }
    },
    [session, actionSubmitting, clearAction, load, clearAuthAndRedirect],
  )

  const runVisitAction = useCallback(
    async (action: (token: string, salonId: string, bookingId: string) => Promise<unknown>, bookingId: string) => {
      if (!session || actionSubmitting) {
        return
      }
      setActionSubmitting(true)
      setActionError(null)
      try {
        await action(session.token, session.salon.salon_id, bookingId)
        clearAction()
        await load()
      } catch (err: unknown) {
        if (isUnauthorizedError(err)) {
          clearAuthAndRedirect()
          return
        }
        setActionError(mapAdminBookingActionError(err))
      } finally {
        setActionSubmitting(false)
      }
    },
    [session, actionSubmitting, clearAction, load, clearAuthAndRedirect],
  )

  const handleConfirmCancel = useCallback(
    async (event: FormEvent) => {
      event.preventDefault()
      if (!session || !actionBooking || actionSubmitting) {
        return
      }
      setActionSubmitting(true)
      setActionError(null)
      try {
        await cancelAdminBooking(
          session.token,
          session.salon.salon_id,
          actionBooking.id,
          { reason: cancelReason.trim() || undefined },
        )
        clearAction()
        await load()
      } catch (err: unknown) {
        if (isUnauthorizedError(err)) {
          clearAuthAndRedirect()
          return
        }
        setActionError(mapAdminBookingActionError(err))
      } finally {
        setActionSubmitting(false)
      }
    },
    [
      session,
      actionBooking,
      actionSubmitting,
      cancelReason,
      clearAction,
      load,
      clearAuthAndRedirect,
    ],
  )

  const handleConfirmReschedule = useCallback(
    async (event: FormEvent) => {
      event.preventDefault()
      if (!session || !actionBooking || actionSubmitting) {
        return
      }
      if (!rescheduleStaffId) {
        setActionError('Select a staff member.')
        return
      }
      if (!rescheduleStartLocal) {
        setActionError('Choose a new service start time.')
        return
      }

      setActionSubmitting(true)
      setActionError(null)
      try {
        await rescheduleAdminBooking(
          session.token,
          session.salon.salon_id,
          actionBooking.id,
          {
            staff_id: rescheduleStaffId,
            service_start: salonLocalDateTimeToIso(rescheduleStartLocal, salonTimeZoneForInput),
          },
        )
        clearAction()
        await load()
      } catch (err: unknown) {
        if (isUnauthorizedError(err)) {
          clearAuthAndRedirect()
          return
        }
        setActionError(mapAdminBookingActionError(err))
        if (isAdminBookingSlotConflictError(err)) {
          setRescheduleStartLocal('')
        }
      } finally {
        setActionSubmitting(false)
      }
    },
    [
      session,
      actionBooking,
      actionSubmitting,
      rescheduleStaffId,
      rescheduleStartLocal,
      salonTimeZoneForInput,
      clearAction,
      load,
      clearAuthAndRedirect,
    ],
  )

  return (
    <AdminLayout>
      <section className="admin-bookings">
        <header className="admin-bookings__header">
          <h1 className="admin-bookings__title">Bookings</h1>
          <p className="admin-bookings__lead">
            {manage
              ? 'View bookings, create appointments, manage visit status, and cancel or reschedule pending and confirmed ones.'
              : 'Read-only list for your salon.'}
          </p>
          {manage && !createOpen && actionMode === null ? (
            <p className="admin-bookings__header-actions">
              <button
                type="button"
                className="btn btn--primary btn--compact"
                onClick={startCreate}
                disabled={actionSubmitting || createSubmitting}
              >
                Create booking
              </button>
            </p>
          ) : null}
        </header>

        <form
          className="admin-bookings__filters"
          onSubmit={(event) => {
            event.preventDefault()
            void load()
          }}
        >
          <label className="admin-bookings__filter">
            <span>From (salon day)</span>
            <input
              type="date"
              value={dateFrom}
              onChange={(event) => setDateFrom(event.target.value)}
            />
          </label>
          <label className="admin-bookings__filter">
            <span>To (salon day)</span>
            <input
              type="date"
              value={dateTo}
              onChange={(event) => setDateTo(event.target.value)}
            />
          </label>
          <label className="admin-bookings__filter">
            <span>Status</span>
            <select
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option.label} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" className="btn btn--secondary btn--compact">
            Apply
          </button>
        </form>

        {manage && createOpen ? (
          <form
            className="admin-bookings__form"
            onSubmit={(event) => void handleConfirmCreate(event)}
          >
            <h2 className="admin-bookings__form-title">Create booking</h2>
            <p className="admin-bookings__form-lead">
              Search for a customer, then choose service, staff, and start time in salon
              timezone ({salonTimeZoneForInput}).
            </p>
            <div className="admin-bookings__form-grid">
              <label className="admin-bookings__filter admin-bookings__filter--wide">
                <span>Customer search</span>
                <input
                  type="search"
                  value={createCustomerSearch}
                  onChange={(event) => setCreateCustomerSearch(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault()
                      void searchCreateCustomers()
                    }
                  }}
                  placeholder="Name, phone, or email"
                  autoComplete="off"
                  disabled={createSubmitting}
                />
              </label>
              <label className="admin-bookings__filter">
                <span>Find</span>
                <button
                  type="button"
                  className="btn btn--secondary btn--compact"
                  onClick={() => void searchCreateCustomers()}
                  disabled={createSubmitting || createCustomersLoading}
                >
                  Search customers
                </button>
              </label>
              <label className="admin-bookings__filter admin-bookings__filter--wide">
                <span>Customer</span>
                <select
                  value={createCustomerId}
                  onChange={(event) => setCreateCustomerId(event.target.value)}
                  disabled={
                    createSubmitting || createCustomersLoading || createCustomers.length === 0
                  }
                  required
                >
                  {createCustomers.length === 0 ? (
                    <option value="">Search to load customers</option>
                  ) : null}
                  {createCustomers.map((customer) => (
                    <option key={customer.id} value={customer.id}>
                      {customer.full_name}
                      {customer.phone ? ` · ${customer.phone}` : ''}
                    </option>
                  ))}
                </select>
              </label>
              <label className="admin-bookings__filter">
                <span>Service</span>
                <select
                  value={createServiceId}
                  onChange={(event) => setCreateServiceId(event.target.value)}
                  disabled={createSubmitting || createServicesLoading || createServices.length === 0}
                  required
                >
                  {createServices.length === 0 ? (
                    <option value="">
                      {createServicesLoading ? 'Loading services…' : 'No active services'}
                    </option>
                  ) : (
                    <>
                      <option value="">Select service</option>
                      {createServices.map((service) => (
                        <option key={service.id} value={service.id}>
                          {service.name} · {service.duration_minutes} min
                        </option>
                      ))}
                    </>
                  )}
                </select>
              </label>
              <label className="admin-bookings__filter">
                <span>Staff</span>
                <select
                  value={createStaffId}
                  onChange={(event) => setCreateStaffId(event.target.value)}
                  disabled={
                    createSubmitting ||
                    createServiceStaffLoading ||
                    staffLoading ||
                    !createServiceId ||
                    createStaffList.length === 0
                  }
                  required
                >
                  {!createServiceId ? (
                    <option value="">Select a service first</option>
                  ) : createStaffList.length === 0 ? (
                    <option value="">
                      {createServiceStaffLoading || staffLoading
                        ? 'Loading staff…'
                        : 'No bookable staff for service'}
                    </option>
                  ) : null}
                  {createStaffList.map((staff) => (
                    <option key={staff.id} value={staff.id}>
                      {staff.display_name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="admin-bookings__filter">
                <span>Service start</span>
                <input
                  type="datetime-local"
                  required
                  value={createStartLocal}
                  onChange={(event) => setCreateStartLocal(event.target.value)}
                  disabled={createSubmitting}
                />
              </label>
              <label className="admin-bookings__filter">
                <span>Status</span>
                <select
                  value={createStatus}
                  onChange={(event) =>
                    setCreateStatus(event.target.value as AdminBookingCreateStatus)
                  }
                  disabled={createSubmitting}
                >
                  {CREATE_STATUS_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="admin-bookings__form-actions">
              <button
                type="submit"
                className="btn btn--primary btn--compact"
                disabled={
                  createSubmitting ||
                  createServicesLoading ||
                  createServices.length === 0 ||
                  createCustomers.length === 0
                }
              >
                Create booking
              </button>
              <button
                type="button"
                className="btn btn--secondary btn--compact"
                onClick={clearCreate}
                disabled={createSubmitting}
              >
                Back
              </button>
            </div>
          </form>
        ) : null}

        {createError ? (
          <p className="admin-bookings__state admin-bookings__state--error" role="alert">
            {createError}
          </p>
        ) : null}

        {manage && actionMode === 'cancel' && actionBooking ? (
          <form
            className="admin-bookings__form"
            onSubmit={(event) => void handleConfirmCancel(event)}
          >
            <h2 className="admin-bookings__form-title">Cancel booking</h2>
            <p className="admin-bookings__form-lead">
              {actionBooking.customer_name} ·{' '}
              {formatBookingDateTime(actionBooking.starts_at, salonTimeZone)} ·{' '}
              {actionBooking.service_name}
            </p>
            <div className="admin-bookings__form-grid">
              <label className="admin-bookings__filter admin-bookings__filter--wide">
                <span>Reason (optional)</span>
                <input
                  type="text"
                  maxLength={255}
                  value={cancelReason}
                  onChange={(event) => setCancelReason(event.target.value)}
                  placeholder="Optional"
                  disabled={actionSubmitting}
                />
              </label>
            </div>
            <div className="admin-bookings__form-actions">
              <button
                type="submit"
                className="btn btn--primary btn--compact"
                disabled={actionSubmitting}
              >
                Confirm cancel
              </button>
              <button
                type="button"
                className="btn btn--secondary btn--compact"
                onClick={clearAction}
                disabled={actionSubmitting}
              >
                Back
              </button>
            </div>
          </form>
        ) : null}

        {manage && actionMode === 'reschedule' && actionBooking ? (
          <form
            className="admin-bookings__form"
            onSubmit={(event) => void handleConfirmReschedule(event)}
          >
            <h2 className="admin-bookings__form-title">Reschedule booking</h2>
            <p className="admin-bookings__form-lead">
              {actionBooking.customer_name} · {actionBooking.service_name} ·{' '}
              {actionBooking.duration_minutes} min
            </p>
            <div className="admin-bookings__form-grid">
              <label className="admin-bookings__filter">
                <span>Staff</span>
                <select
                  value={rescheduleStaffId}
                  onChange={(event) => setRescheduleStaffId(event.target.value)}
                  disabled={actionSubmitting || staffLoading || staffList.length === 0}
                  required
                >
                  {staffList.length === 0 ? (
                    <option value="">No bookable staff</option>
                  ) : null}
                  {staffList.map((staff) => (
                    <option key={staff.id} value={staff.id}>
                      {staff.display_name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="admin-bookings__filter">
                <span>Service start</span>
                <input
                  type="datetime-local"
                  required
                  value={rescheduleStartLocal}
                  onChange={(event) => setRescheduleStartLocal(event.target.value)}
                  disabled={actionSubmitting}
                />
              </label>
            </div>
            <div className="admin-bookings__form-actions">
              <button
                type="submit"
                className="btn btn--primary btn--compact"
                disabled={
                  actionSubmitting || staffLoading || staffList.length === 0
                }
              >
                Confirm reschedule
              </button>
              <button
                type="button"
                className="btn btn--secondary btn--compact"
                onClick={clearAction}
                disabled={actionSubmitting}
              >
                Back
              </button>
            </div>
          </form>
        ) : null}

        {actionError ? (
          <p className="admin-bookings__state admin-bookings__state--error" role="alert">
            {actionError}
          </p>
        ) : null}

        {loading ? (
          <p className="admin-bookings__state" role="status">
            Loading bookings…
          </p>
        ) : null}

        {!loading && error ? (
          <p className="admin-bookings__state admin-bookings__state--error" role="alert">
            {error}
          </p>
        ) : null}

        {!loading && !error && items.length === 0 ? (
          <p className="admin-bookings__state">No bookings match your filters.</p>
        ) : null}

        {!loading && !error && items.length > 0 ? (
          <div className="admin-bookings__table-wrap">
            <table className="admin-bookings__table">
              <thead>
                <tr>
                  <th scope="col">When</th>
                  <th scope="col">Customer</th>
                  <th scope="col">Service</th>
                  <th scope="col">Staff</th>
                  <th scope="col">Status</th>
                  <th scope="col">Price</th>
                  {manage ? <th scope="col">Actions</th> : null}
                </tr>
              </thead>
              <tbody>
                {items.map((row) => {
                  const actionable = isActionableBookingStatus(row.status)
                  const visitActions = hasVisitLifecycleActions(row.status)
                  const isActiveRow = actionBooking?.id === row.id
                  const actionsBusy =
                    actionSubmitting ||
                    createSubmitting ||
                    createOpen ||
                    actionMode !== null
                  return (
                    <tr key={row.id}>
                      <td>{formatBookingDateTime(row.starts_at, salonTimeZone)}</td>
                      <td>
                        <span className="admin-bookings__customer-name">{row.customer_name}</span>
                        {row.customer_phone ? (
                          <span className="admin-bookings__customer-phone">{row.customer_phone}</span>
                        ) : null}
                      </td>
                      <td>{row.service_name}</td>
                      <td>{row.staff_name}</td>
                      <td>
                        <span className="admin-bookings__status">{row.status.replace('_', ' ')}</span>
                      </td>
                      <td>{formatDashboardPrice(row.price_cents, salonCurrencyCode)}</td>
                      {manage ? (
                        <td className="admin-bookings__actions">
                          {actionable ? (
                            <>
                              {row.status === 'pending' ? (
                                <button
                                  type="button"
                                  className="btn btn--primary btn--compact"
                                  onClick={() => void handleConfirmPending(row)}
                                  disabled={actionsBusy}
                                >
                                  Confirm
                                </button>
                              ) : null}
                              <button
                                type="button"
                                className="btn btn--secondary btn--compact"
                                onClick={() => startReschedule(row)}
                                disabled={
                                  actionSubmitting ||
                                  createSubmitting ||
                                  createOpen ||
                                  (isActiveRow && actionMode === 'reschedule')
                                }
                              >
                                Reschedule
                              </button>
                              <button
                                type="button"
                                className="btn btn--secondary btn--compact"
                                onClick={() => startCancel(row)}
                                disabled={
                                  actionSubmitting ||
                                  createSubmitting ||
                                  createOpen ||
                                  (isActiveRow && actionMode === 'cancel')
                                }
                              >
                                Cancel
                              </button>
                            </>
                          ) : null}
                          {visitActions ? (
                            <>
                              {row.status === 'confirmed' ? (
                                <button
                                  type="button"
                                  className="btn btn--primary btn--compact"
                                  onClick={() =>
                                    void runVisitAction(startAdminVisit, row.id)
                                  }
                                  disabled={actionsBusy}
                                >
                                  Start visit
                                </button>
                              ) : null}
                              {row.status === 'in_progress' ? (
                                <button
                                  type="button"
                                  className="btn btn--primary btn--compact"
                                  onClick={() =>
                                    void runVisitAction(completeAdminVisit, row.id)
                                  }
                                  disabled={actionsBusy}
                                >
                                  Complete
                                </button>
                              ) : null}
                              {row.status === 'confirmed' ? (
                                <button
                                  type="button"
                                  className="btn btn--secondary btn--compact"
                                  onClick={() =>
                                    void runVisitAction(markAdminNoShow, row.id)
                                  }
                                  disabled={actionsBusy}
                                >
                                  No show
                                </button>
                              ) : null}
                            </>
                          ) : null}
                          {!actionable && !visitActions ? (
                            <span className="admin-bookings__actions-muted">—</span>
                          ) : null}
                        </td>
                      ) : null}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </AdminLayout>
  )
}
