import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getPublicSalon, getPublicServices } from '../api/publicSalon'
import { ApiError } from '../api/errors'
import { ErrorState } from '../components/ErrorState'
import { LoadingState } from '../components/LoadingState'
import { SalonHeader } from '../components/SalonHeader'
import {
  ServiceList,
  type ServiceListState,
} from '../components/ServiceList'
import type { PublicSalonEntryResponse } from '../types/publicSalon'

type SalonLoadState =
  | { status: 'loading' }
  | { status: 'success'; salon: PublicSalonEntryResponse }
  | { status: 'error'; statusCode: number; message: string }

export function PublicSalonPage() {
  const { slug } = useParams<{ slug: string }>()
  const [salonState, setSalonState] = useState<SalonLoadState>({
    status: 'loading',
  })
  const [servicesState, setServicesState] = useState<ServiceListState>({
    status: 'idle',
  })

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

  return (
    <main className="page public-salon-page">
      <SalonHeader name={salonState.salon.name} />
      <section className="public-salon-page__services" aria-label="Services">
        <ServiceList state={servicesState} />
      </section>
    </main>
  )
}
