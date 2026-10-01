import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  createPublicBookingBySlug,
  getPublicSalon,
  getPublicServiceAvailability,
  getPublicServices,
  getPublicServiceStaff,
  lookupPublicCustomer,
  mapServiceAvailabilityToSelectedSlots,
} from '../api/publicSalon'
import { ApiError } from '../api/errors'
import {
  AvailabilityTimeList,
  type AvailabilityTimeListState,
} from '../components/AvailabilityTimeList'
import { BookingConfirmation } from '../components/BookingConfirmation'
import { BookingSummary } from '../components/BookingSummary'
import { CustomerDetailsForm } from '../components/CustomerDetailsForm'
import { DateSelector } from '../components/DateSelector'
import { ErrorState } from '../components/ErrorState'
import { LoadingState } from '../components/LoadingState'
import { SalonHeader } from '../components/SalonHeader'
import { SelectedServiceBar } from '../components/SelectedServiceBar'
import {
  ServiceList,
  type ServiceListState,
} from '../components/ServiceList'
import {
  ServiceStaffList,
  type ServiceStaffListState,
} from '../components/ServiceStaffList'
import type { PublicCatalogServiceWithMedia } from '../types/publicCatalog'
import type {
  CustomerFormFieldErrors,
  CustomerFormState,
  PublicBookingCreateResponse,
} from '../types/publicBooking'
import { EMPTY_CUSTOMER_FORM } from '../types/publicBooking'
import type {
  BookingWizardStep,
  PublicSalonWithMedia,
  PublicSelectedSlot,
} from '../types/publicSalon'
import { ANY_STAFF_CHOICE_ID } from '../types/publicSalon'
import { defaultDateInTimeZone } from '../utils/date'
import { persistManageSnapshot } from '../utils/manageBookingStorage'
import {
  isSlotConflictError,
  mapPublicBookingError,
} from '../utils/mapPublicBookingError'
import {
  customerFormHasErrors,
  isCustomerPhoneLookupEligible,
  validateCustomerForm,
} from '../utils/validateCustomerForm'

const CUSTOMER_PHONE_LOOKUP_DEBOUNCE_MS = 500

type SalonLoadState =
  | { status: 'loading' }
  | { status: 'success'; salon: PublicSalonWithMedia }
  | { status: 'error'; statusCode: number; message: string }

type StaffChoice =
  | { kind: 'any' }
  | { kind: 'specific'; staffId: string }

function resetCustomerBookingState(): {
  customerForm: CustomerFormState
  fieldErrors: CustomerFormFieldErrors
  submitError: string | null
  bookingResult: PublicBookingCreateResponse | null
  submitting: boolean
} {
  return {
    customerForm: { ...EMPTY_CUSTOMER_FORM },
    fieldErrors: {},
    submitError: null,
    bookingResult: null,
    submitting: false,
  }
}

function staffChoiceToSelectedId(choice: StaffChoice | null): string | null {
  if (choice === null) {
    return null
  }
  if (choice.kind === 'any') {
    return ANY_STAFF_CHOICE_ID
  }
  return choice.staffId
}

function resolveStaffDisplayName(
  staffState: ServiceStaffListState,
  staffId: string,
): string {
  if (staffState.status === 'success') {
    const member = staffState.staff.find((s) => s.id === staffId)
    if (member) {
      return member.display_name
    }
  }
  return 'Мастер'
}

export function PublicSalonPage() {
  const { slug } = useParams<{ slug: string }>()
  const [salonState, setSalonState] = useState<SalonLoadState>({
    status: 'loading',
  })
  const [servicesState, setServicesState] = useState<ServiceListState>({
    status: 'idle',
  })
  const [selectedService, setSelectedService] =
    useState<PublicCatalogServiceWithMedia | null>(null)
  const [staffState, setStaffState] = useState<ServiceStaffListState>({
    status: 'idle',
  })
  const [staffChoice, setStaffChoice] = useState<StaffChoice | null>(null)
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [selectedSlot, setSelectedSlot] = useState<PublicSelectedSlot | null>(
    null,
  )
  const [availabilityState, setAvailabilityState] =
    useState<AvailabilityTimeListState>({ status: 'idle' })
  const [availabilityNonce, setAvailabilityNonce] = useState(0)
  const [flowStep, setFlowStep] = useState<BookingWizardStep>('staff')
  const [customerForm, setCustomerForm] =
    useState<CustomerFormState>(EMPTY_CUSTOMER_FORM)
  const [fieldErrors, setFieldErrors] = useState<CustomerFormFieldErrors>({})
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [bookingResult, setBookingResult] =
    useState<PublicBookingCreateResponse | null>(null)
  const [phoneLookupPending, setPhoneLookupPending] = useState(false)
  const submitInFlightRef = useRef(false)
  const userEditedNameRef = useRef(false)
  const customerLookupAbortRef = useRef<AbortController | null>(null)
  const customerLookupSeqRef = useRef(0)

  const salonTimeZone =
    salonState.status === 'success' ? salonState.salon.timezone : 'UTC'

  useEffect(() => {
    if (!slug) {
      setSalonState({
        status: 'error',
        statusCode: 404,
        message: 'Salon not found',
      })
      return
    }

    let cancelled = false
    setSalonState({ status: 'loading' })
    setServicesState({ status: 'idle' })
    setSelectedService(null)
    setStaffState({ status: 'idle' })
    setStaffChoice(null)
    setSelectedDate(null)
    setSelectedSlot(null)
    setAvailabilityState({ status: 'idle' })
    setAvailabilityNonce(0)
    setFlowStep('staff')
    const reset = resetCustomerBookingState()
    setCustomerForm(reset.customerForm)
    setFieldErrors(reset.fieldErrors)
    setSubmitError(reset.submitError)
    setBookingResult(reset.bookingResult)
    setSubmitting(reset.submitting)
    userEditedNameRef.current = false
    customerLookupAbortRef.current?.abort()
    customerLookupAbortRef.current = null
    customerLookupSeqRef.current += 1
    setPhoneLookupPending(false)

    getPublicSalon(slug)
      .then((salon) => {
        if (!cancelled) {
          setSalonState({ status: 'success', salon })
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 404) {
          setSalonState({
            status: 'error',
            statusCode: 404,
            message: 'Salon not found',
          })
          return
        }
        const message =
          err instanceof ApiError ? err.message : 'Something went wrong'
        setSalonState({
          status: 'error',
          statusCode: err instanceof ApiError ? err.status : 0,
          message,
        })
      })

    return () => {
      cancelled = true
    }
  }, [slug])

  useEffect(() => {
    if (!slug || flowStep !== 'customer') {
      customerLookupAbortRef.current?.abort()
      customerLookupAbortRef.current = null
      setPhoneLookupPending(false)
      return
    }

    const trimmedPhone = customerForm.phone.trim()
    if (!isCustomerPhoneLookupEligible(trimmedPhone)) {
      customerLookupAbortRef.current?.abort()
      customerLookupAbortRef.current = null
      setPhoneLookupPending(false)
      return
    }

    const debounceTimer = window.setTimeout(() => {
      customerLookupAbortRef.current?.abort()
      const controller = new AbortController()
      customerLookupAbortRef.current = controller
      const seq = (customerLookupSeqRef.current += 1)
      setPhoneLookupPending(true)

      void lookupPublicCustomer(slug, trimmedPhone, controller.signal)
        .then((result) => {
          if (seq !== customerLookupSeqRef.current) {
            return
          }
          if (
            result.found &&
            result.full_name !== null &&
            !userEditedNameRef.current
          ) {
            setCustomerForm((prev) => ({
              ...prev,
              full_name: result.full_name ?? prev.full_name,
            }))
          }
        })
        .catch((err: unknown) => {
          if (err instanceof DOMException && err.name === 'AbortError') {
            return
          }
          /* lookup failure is silent and non-blocking */
        })
        .finally(() => {
          if (seq === customerLookupSeqRef.current) {
            setPhoneLookupPending(false)
          }
        })
    }, CUSTOMER_PHONE_LOOKUP_DEBOUNCE_MS)

    return () => {
      window.clearTimeout(debounceTimer)
    }
  }, [slug, flowStep, customerForm.phone])

  useEffect(() => {
    if (salonState.status !== 'success' || !slug) {
      return
    }

    let cancelled = false
    setServicesState({ status: 'loading' })

    getPublicServices(slug)
      .then((result) => {
        if (!cancelled) {
          setServicesState({
            status: 'success',
            services: result.services,
          })
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const message =
          err instanceof ApiError ? err.message : 'Something went wrong'
        setServicesState({ status: 'error', message })
      })

    return () => {
      cancelled = true
    }
  }, [slug, salonState.status])

  useEffect(() => {
    if (!slug || !selectedService) {
      setStaffState({ status: 'idle' })
      return
    }

    let cancelled = false
    setStaffState({ status: 'loading' })

    getPublicServiceStaff(slug, selectedService.id)
      .then((result) => {
        if (!cancelled) {
          setStaffState({ status: 'success', staff: result.staff })
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const message =
          err instanceof ApiError ? err.message : 'Something went wrong'
        setStaffState({ status: 'error', message })
      })

    return () => {
      cancelled = true
    }
  }, [slug, selectedService])

  useEffect(() => {
    if (
      !slug ||
      !selectedService ||
      staffChoice === null ||
      selectedDate === null ||
      flowStep !== 'time'
    ) {
      if (flowStep !== 'time') {
        setAvailabilityState({ status: 'idle' })
      }
      return
    }

    let cancelled = false
    setAvailabilityState({ status: 'loading' })

    const staffIdForQuery =
      staffChoice.kind === 'specific' ? staffChoice.staffId : undefined

    getPublicServiceAvailability(slug, {
      serviceId: selectedService.id,
      staffId: staffIdForQuery,
      startDate: selectedDate,
      endDate: selectedDate,
    })
      .then((result) => {
        if (cancelled) return
        setAvailabilityState({
          status: 'success',
          slots: mapServiceAvailabilityToSelectedSlots(
            result,
            staffIdForQuery,
          ),
        })
      })
      .catch(() => {
        if (cancelled) return
        setAvailabilityState({ status: 'error' })
      })

    return () => {
      cancelled = true
    }
  }, [
    slug,
    selectedService,
    staffChoice,
    selectedDate,
    flowStep,
    availabilityNonce,
  ])

  const applyCustomerReset = useCallback(() => {
    const reset = resetCustomerBookingState()
    setCustomerForm(reset.customerForm)
    setFieldErrors(reset.fieldErrors)
    setSubmitError(reset.submitError)
    setBookingResult(reset.bookingResult)
    setSubmitting(reset.submitting)
    submitInFlightRef.current = false
    userEditedNameRef.current = false
    customerLookupAbortRef.current?.abort()
    customerLookupAbortRef.current = null
    customerLookupSeqRef.current += 1
    setPhoneLookupPending(false)
  }, [])

  const handleSelectService = useCallback(
    (service: PublicCatalogServiceWithMedia) => {
      setSelectedService(service)
      setStaffChoice(null)
      setSelectedDate(null)
      setSelectedSlot(null)
      setAvailabilityState({ status: 'idle' })
      setAvailabilityNonce(0)
      setFlowStep('staff')
      applyCustomerReset()
    },
    [applyCustomerReset],
  )

  const handleBackToServices = useCallback(() => {
    setSelectedService(null)
    setStaffChoice(null)
    setSelectedDate(null)
    setSelectedSlot(null)
    setStaffState({ status: 'idle' })
    setAvailabilityState({ status: 'idle' })
    setAvailabilityNonce(0)
    setFlowStep('staff')
    applyCustomerReset()
  }, [applyCustomerReset])

  const handleSelectStaff = useCallback(
    (staffId: string) => {
      setStaffChoice({ kind: 'specific', staffId })
      setSelectedSlot(null)
      setSelectedDate(defaultDateInTimeZone(salonTimeZone))
      setSubmitError(null)
      setFlowStep('date')
      applyCustomerReset()
    },
    [applyCustomerReset, salonTimeZone],
  )

  const handleSelectAnyStaff = useCallback(() => {
    setStaffChoice({ kind: 'any' })
    setSelectedSlot(null)
    setSelectedDate(defaultDateInTimeZone(salonTimeZone))
    setSubmitError(null)
    setFlowStep('date')
    applyCustomerReset()
  }, [applyCustomerReset, salonTimeZone])

  const handleSelectDate = useCallback((isoDate: string) => {
    setSelectedDate(isoDate)
    setSelectedSlot(null)
    setSubmitError(null)
    setFlowStep('time')
  }, [])

  const handleSelectSlot = useCallback((slot: PublicSelectedSlot) => {
    setSelectedSlot(slot)
    setSubmitError(null)
    setFlowStep('time')
  }, [])

  const handleNextToCustomer = useCallback(() => {
    if (selectedSlot === null) {
      return
    }
    setSubmitError(null)
    setFlowStep('customer')
  }, [selectedSlot])

  const handleBackToStaff = useCallback(() => {
    setSubmitError(null)
    setFlowStep('staff')
  }, [])

  const handleBackToDate = useCallback(() => {
    setSelectedSlot(null)
    setSubmitError(null)
    setFlowStep('date')
  }, [])

  const handleBackToTime = useCallback(() => {
    setSubmitError(null)
    setFlowStep('time')
  }, [])

  const handleCustomerFieldChange = useCallback(
    (field: keyof CustomerFormState, value: string) => {
      if (field === 'full_name') {
        userEditedNameRef.current = true
      }
      setCustomerForm((prev) => ({ ...prev, [field]: value }))
      setFieldErrors((prev) => {
        if (!prev[field]) {
          return prev
        }
        const next = { ...prev }
        delete next[field]
        return next
      })
    },
    [],
  )

  const handleSubmitBooking = useCallback(async () => {
    if (
      !slug ||
      !selectedService ||
      staffChoice === null ||
      selectedDate === null ||
      selectedSlot === null ||
      submitInFlightRef.current
    ) {
      return
    }

    const errors = validateCustomerForm(customerForm)
    if (customerFormHasErrors(errors)) {
      setFieldErrors(errors)
      return
    }

    submitInFlightRef.current = true
    setSubmitting(true)
    setSubmitError(null)

    try {
      const result = await createPublicBookingBySlug(slug, {
        full_name: customerForm.full_name.trim(),
        phone: customerForm.phone.trim(),
        customer_notes: customerForm.customer_notes.trim() || undefined,
        service_id: selectedService.id,
        staff_id: selectedSlot.staff_id,
        service_start: selectedSlot.service_start,
      })
      persistManageSnapshot({
        token: result.manage_token,
        booking_id: result.booking_id,
        slug,
        salon_id: result.salon_id,
        service_id: selectedService.id,
        staff_id: selectedSlot.staff_id,
        service_name: selectedService.name,
        staff_display_name: resolveStaffDisplayName(
          staffState,
          selectedSlot.staff_id,
        ),
        service_start: result.service_start,
        service_end: result.service_end,
        hold_expires_at: result.hold_expires_at,
      })
      setBookingResult(result)
      setFlowStep('confirmation')
    } catch (err: unknown) {
      setSubmitError(mapPublicBookingError(err))
      if (isSlotConflictError(err)) {
        setSelectedSlot(null)
        setAvailabilityNonce((n) => n + 1)
        setFlowStep('time')
      }
    } finally {
      setSubmitting(false)
      submitInFlightRef.current = false
    }
  }, [
    slug,
    selectedService,
    staffChoice,
    selectedDate,
    selectedSlot,
    customerForm,
    staffState,
  ])

  const handleBookingDone = useCallback(() => {
    handleBackToServices()
  }, [handleBackToServices])

  if (salonState.status === 'loading') {
    return (
      <main className="page">
        <LoadingState message="Loading salon…" />
      </main>
    )
  }

  if (salonState.status === 'error') {
    const title =
      salonState.statusCode === 404 ? 'Salon not found' : 'Something went wrong'
    return (
      <main className="page">
        <ErrorState title={title} message={salonState.message} />
      </main>
    )
  }

  const showBookingWizard = selectedService !== null
  const selectedStaffListId = staffChoiceToSelectedId(staffChoice)

  return (
    <main className="page public-salon-page">
      <SalonHeader
        name={salonState.salon.name}
        logoUrl={salonState.salon.logo_url}
      />

      {showBookingWizard ? (
        <section
          className="public-salon-page__booking booking-step"
          aria-label="Booking"
        >
          <SelectedServiceBar service={selectedService} />

          {flowStep === 'confirmation' && bookingResult !== null ? (
            <BookingConfirmation
              booking={bookingResult}
              slug={slug ?? ''}
              timeZone={salonTimeZone}
              onDone={handleBookingDone}
            />
          ) : flowStep === 'customer' &&
            staffChoice !== null &&
            selectedDate !== null &&
            selectedSlot !== null ? (
            <>
              <BookingSummary
                service={selectedService}
                staffDisplayName={resolveStaffDisplayName(
                  staffState,
                  selectedSlot.staff_id,
                )}
                selectedDate={selectedDate}
                serviceStartIso={selectedSlot.service_start}
                timeZone={salonTimeZone}
              />
              <CustomerDetailsForm
                form={customerForm}
                fieldErrors={fieldErrors}
                disabled={submitting}
                phoneLookupPending={phoneLookupPending}
                onChange={handleCustomerFieldChange}
              />
              {submitError ? (
                <div className="form-error-banner" role="alert">
                  <p>{submitError}</p>
                </div>
              ) : null}
              <div className="booking-step__actions">
                <button
                  type="button"
                  className="btn btn--secondary"
                  disabled={submitting}
                  onClick={handleBackToTime}
                >
                  К выбору времени
                </button>
                <button
                  type="button"
                  className="btn btn--primary btn--block"
                  disabled={submitting}
                  onClick={() => void handleSubmitBooking()}
                >
                  {submitting ? 'Отправка…' : 'Записаться'}
                </button>
              </div>
            </>
          ) : flowStep === 'time' &&
            staffChoice !== null &&
            selectedDate !== null ? (
            <>
              <h2 className="booking-step__heading">Выберите время</h2>
              {submitError ? (
                <div className="form-error-banner" role="alert">
                  <p>{submitError}</p>
                </div>
              ) : null}
              <AvailabilityTimeList
                state={availabilityState}
                selectedSlot={selectedSlot}
                timeZone={salonTimeZone}
                onSelectSlot={handleSelectSlot}
              />
              <div className="booking-step__actions">
                <button
                  type="button"
                  className="btn btn--secondary"
                  onClick={handleBackToDate}
                >
                  К выбору даты
                </button>
                <button
                  type="button"
                  className="btn btn--primary"
                  disabled={selectedSlot === null}
                  onClick={handleNextToCustomer}
                >
                  Далее: ваши данные
                </button>
              </div>
            </>
          ) : flowStep === 'date' && staffChoice !== null ? (
            <>
              <h2 className="booking-step__heading">Выберите дату</h2>
              <DateSelector
                selectedDate={
                  selectedDate ?? defaultDateInTimeZone(salonTimeZone)
                }
                timeZone={salonTimeZone}
                onSelectDate={handleSelectDate}
              />
              <div className="booking-step__actions">
                <button
                  type="button"
                  className="btn btn--secondary"
                  onClick={handleBackToStaff}
                >
                  К выбору мастера
                </button>
              </div>
            </>
          ) : (
            <>
              <h2 className="booking-step__heading">Выберите мастера</h2>
              <ServiceStaffList
                state={staffState}
                selectedStaffId={selectedStaffListId}
                onSelectStaff={(member) => handleSelectStaff(member.id)}
                onSelectAnyStaff={handleSelectAnyStaff}
              />
              <div className="booking-step__actions">
                <button
                  type="button"
                  className="btn btn--secondary"
                  onClick={handleBackToServices}
                >
                  К услугам
                </button>
              </div>
            </>
          )}
        </section>
      ) : (
        <section className="public-salon-page__services" aria-label="Services">
          <ServiceList
            state={servicesState}
            selectedServiceId={null}
            onSelectService={handleSelectService}
          />
        </section>
      )}
    </main>
  )
}
