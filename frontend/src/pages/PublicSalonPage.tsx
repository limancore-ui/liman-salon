import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
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
import type { PublicSalonEntryResponse } from '../types/publicSalon'
import { toIsoDateLocal } from '../utils/date'

type SalonLoadState =
  | { status: 'loading' }
  | { status: 'success'; salon: PublicSalonEntryResponse }
  | { status: 'error'; statusCode: number; message: string }

function defaultSelectedDate(): string {
  return toIsoDateLocal(new Date())
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

  const handleSelectService = useCallback(
    (service: PublicCatalogServiceOut) => {
      setSelectedService(service)
      setSelectedStaff(null)
      setSelectedDate(null)
      setSelectedTime(null)
      setAvailabilityState({ status: 'idle' })
    },
    [],
  )

  const handleBackToServices = useCallback(() => {
    setSelectedService(null)
    setSelectedStaff(null)
    setSelectedDate(null)
    setSelectedTime(null)
    setStaffState({ status: 'idle' })
    setAvailabilityState({ status: 'idle' })
  }, [])

  const handleSelectStaff = useCallback((staff: PublicCatalogStaffOut) => {
    setSelectedStaff(staff)
    setSelectedTime(null)
    setSelectedDate((prev) => prev ?? defaultSelectedDate())
  }, [])

  const handleSelectDate = useCallback((isoDate: string) => {
    setSelectedDate(isoDate)
    setSelectedTime(null)
  }, [])

  const handleSelectTime = useCallback((slot: ServiceAvailabilitySlotOut) => {
    setSelectedTime(slot)
  }, [])

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
          <div className="booking-step__context">
            <p className="booking-step__service-name">{selectedService.name}</p>
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
              Back to services
            </button>
            <button
              type="button"
              className="btn btn--primary"
              disabled={selectedTime === null}
            >
              Next: customer details
            </button>
          </div>
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
