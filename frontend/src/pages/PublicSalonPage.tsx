import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  createPublicBookingBySlug,
  getPublicSalon,
  getPublicServiceAvailability,
  getPublicServices,
  getPublicServiceStaff,
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
import {
  ServiceList,
  type ServiceListState,
} from '../components/ServiceList'
import {
  ServiceStaffList,
  type ServiceStaffListState,
} from '../components/ServiceStaffList'
import type {
  PublicCatalogServiceOut,
  PublicCatalogStaffOut,
  ServiceAvailabilitySlotOut,
} from '../types/publicCatalog'
import type {
  CustomerFormFieldErrors,
  CustomerFormState,
  PublicBookingCreateResponse,
} from '../types/publicBooking'
import { EMPTY_CUSTOMER_FORM } from '../types/publicBooking'
import type { PublicSalonEntryResponse } from '../types/publicSalon'
import { toIsoDateLocal } from '../utils/date'
import {
  isSlotConflictError,
  mapPublicBookingError,
} from '../utils/mapPublicBookingError'
import {
  customerFormHasErrors,
  validateCustomerForm,
} from '../utils/validateCustomerForm'

type SalonLoadState =
  | { status: 'loading' }
  | { status: 'success'; salon: PublicSalonEntryResponse }
  | { status: 'error'; statusCode: number; message: string }

type BookingFlowStep = 'schedule' | 'customer' | 'confirmation'

function defaultSelectedDate(): string {
  return toIsoDateLocal(new Date())
}

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

export function PublicSalonPage() {
  const { slug } = useParams<{ slug: string }>()
  const [salonState, setSalonState] = useState<SalonLoadState>({
    status: 'loading',
  })
  const [servicesState, setServicesState] = useState<ServiceListState>({
    status: 'idle',
  })
  const [selectedService, setSelectedService] =
    useState<PublicCatalogServiceOut | null>(null)
  const [staffState, setStaffState] = useState<ServiceStaffListState>({
    status: 'idle',
  })
  const [selectedStaff, setSelectedStaff] =
    useState<PublicCatalogStaffOut | null>(null)
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [selectedTime, setSelectedTime] =
    useState<ServiceAvailabilitySlotOut | null>(null)
  const [availabilityState, setAvailabilityState] =
    useState<AvailabilityTimeListState>({ status: 'idle' })
  const [flowStep, setFlowStep] = useState<BookingFlowStep>('schedule')
  const [customerForm, setCustomerForm] =
    useState<CustomerFormState>(EMPTY_CUSTOMER_FORM)
  const [fieldErrors, setFieldErrors] = useState<CustomerFormFieldErrors>({})
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [bookingResult, setBookingResult] =
    useState<PublicBookingCreateResponse | null>(null)
  const [slotNeedsRefresh, setSlotNeedsRefresh] = useState(false)
  const submitInFlightRef = useRef(false)

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
    setSelectedStaff(null)
    setSelectedDate(null)
    setSelectedTime(null)
    setAvailabilityState({ status: 'idle' })
    setFlowStep('schedule')
    const reset = resetCustomerBookingState()
    setCustomerForm(reset.customerForm)
    setFieldErrors(reset.fieldErrors)
    setSubmitError(reset.submitError)
    setBookingResult(reset.bookingResult)
    setSubmitting(reset.submitting)
    setSlotNeedsRefresh(false)

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
      !selectedStaff ||
      selectedDate === null
    ) {
      setAvailabilityState({ status: 'idle' })
      return
    }

    let cancelled = false
    setAvailabilityState({ status: 'loading' })

    getPublicServiceAvailability(slug, {
      serviceId: selectedService.id,
      staffId: selectedStaff.id,
      startDate: selectedDate,
      endDate: selectedDate,
    })
      .then((result) => {
        if (cancelled) return
        const row = result.staff.find(
          (entry) => entry.staff_id === selectedStaff.id,
        )
        setAvailabilityState({
          status: 'success',
          slots: row?.slots ?? [],
        })
      })
      .catch(() => {
        if (cancelled) return
        setAvailabilityState({ status: 'error' })
      })

    return () => {
      cancelled = true
    }
  }, [slug, selectedService, selectedStaff, selectedDate])

  const applyCustomerReset = useCallback(() => {
    const reset = resetCustomerBookingState()
    setCustomerForm(reset.customerForm)
    setFieldErrors(reset.fieldErrors)
    setSubmitError(reset.submitError)
    setBookingResult(reset.bookingResult)
    setSubmitting(reset.submitting)
    setSlotNeedsRefresh(false)
    submitInFlightRef.current = false
  }, [])

  const handleSelectService = useCallback(
    (service: PublicCatalogServiceOut) => {
      setSelectedService(service)
      setSelectedStaff(null)
      setSelectedDate(null)
      setSelectedTime(null)
      setAvailabilityState({ status: 'idle' })
      setFlowStep('schedule')
      applyCustomerReset()
    },
    [applyCustomerReset],
  )

  const handleBackToServices = useCallback(() => {
    setSelectedService(null)
    setSelectedStaff(null)
    setSelectedDate(null)
    setSelectedTime(null)
    setStaffState({ status: 'idle' })
    setAvailabilityState({ status: 'idle' })
    setFlowStep('schedule')
    applyCustomerReset()
  }, [applyCustomerReset])

  const handleSelectStaff = useCallback(
    (staff: PublicCatalogStaffOut) => {
      setSelectedStaff(staff)
      setSelectedTime(null)
      setSelectedDate((prev) => prev ?? defaultSelectedDate())
      setFlowStep('schedule')
      applyCustomerReset()
    },
    [applyCustomerReset],
  )

  const handleSelectDate = useCallback((isoDate: string) => {
    setSelectedDate(isoDate)
    setSelectedTime(null)
    setSubmitError(null)
    setFlowStep('schedule')
  }, [])

  const handleSelectTime = useCallback((slot: ServiceAvailabilitySlotOut) => {
    setSelectedTime(slot)
    setSubmitError(null)
    setSlotNeedsRefresh(false)
    setFlowStep('schedule')
  }, [])

  const handleNextToCustomer = useCallback(() => {
    if (selectedTime === null) {
      return
    }
    setSubmitError(null)
    setFlowStep('customer')
  }, [selectedTime])

  const handleBackToSchedule = useCallback(() => {
    setSubmitError(null)
    setFlowStep('schedule')
  }, [])

  const handleCustomerFieldChange = useCallback(
    (field: keyof CustomerFormState, value: string) => {
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
      !selectedStaff ||
      selectedDate === null ||
      selectedTime === null ||
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
        staff_id: selectedStaff.id,
        service_start: selectedTime.service_start,
      })
      setBookingResult(result)
      setFlowStep('confirmation')
    } catch (err: unknown) {
      setSubmitError(mapPublicBookingError(err))
      if (isSlotConflictError(err)) {
        setSlotNeedsRefresh(true)
      }
    } finally {
      setSubmitting(false)
      submitInFlightRef.current = false
    }
  }, [
    slug,
    selectedService,
    selectedStaff,
    selectedDate,
    selectedTime,
    customerForm,
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

  const showBookingStep = selectedService !== null

  return (
    <main className="page public-salon-page">
      <SalonHeader name={salonState.salon.name} />

      {showBookingStep ? (
        <section
          className="public-salon-page__booking booking-step"
          aria-label="Booking"
        >
          {flowStep === 'confirmation' && bookingResult !== null ? (
            <BookingConfirmation
              booking={bookingResult}
              onDone={handleBookingDone}
            />
          ) : flowStep === 'customer' &&
            selectedStaff !== null &&
            selectedDate !== null &&
            selectedTime !== null ? (
            <>
              <div className="booking-step__context">
                <p className="booking-step__service-name">
                  {selectedService.name}
                </p>
              </div>
              <BookingSummary
                service={selectedService}
                staff={selectedStaff}
                selectedDate={selectedDate}
                serviceStartIso={selectedTime.service_start}
              />
              <CustomerDetailsForm
                form={customerForm}
                fieldErrors={fieldErrors}
                disabled={submitting}
                onChange={handleCustomerFieldChange}
              />
              {submitError ? (
                <div className="form-error-banner" role="alert">
                  <p>{submitError}</p>
                  {slotNeedsRefresh ? (
                    <button
                      type="button"
                      className="btn btn--secondary btn--compact"
                      onClick={handleBackToSchedule}
                    >
                      Выбрать другое время
                    </button>
                  ) : null}
                </div>
              ) : null}
              <div className="booking-step__actions">
                <button
                  type="button"
                  className="btn btn--secondary"
                  disabled={submitting}
                  onClick={handleBackToSchedule}
                >
                  К выбору времени
                </button>
                <button
                  type="button"
                  className="btn btn--primary btn--block"
                  disabled={submitting || slotNeedsRefresh}
                  onClick={() => void handleSubmitBooking()}
                >
                  {submitting ? 'Отправка…' : 'Записаться'}
                </button>
              </div>
            </>
          ) : (
            <>
              <div className="booking-step__context">
                <p className="booking-step__service-name">
                  {selectedService.name}
                </p>
              </div>
              <h2 className="booking-step__heading">Выберите мастера</h2>
              <ServiceStaffList
                state={staffState}
                selectedStaffId={selectedStaff?.id ?? null}
                onSelectStaff={handleSelectStaff}
              />

              {selectedStaff !== null && selectedDate !== null ? (
                <>
                  <DateSelector
                    selectedDate={selectedDate}
                    onSelectDate={handleSelectDate}
                  />
                  <AvailabilityTimeList
                    state={availabilityState}
                    selectedSlot={selectedTime}
                    onSelectSlot={handleSelectTime}
                  />
                </>
              ) : null}

              <div className="booking-step__actions">
                <button
                  type="button"
                  className="btn btn--secondary"
                  onClick={handleBackToServices}
                >
                  К услугам
                </button>
                <button
                  type="button"
                  className="btn btn--primary"
                  disabled={selectedTime === null}
                  onClick={handleNextToCustomer}
                >
                  Далее: ваши данные
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
