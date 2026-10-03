import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import {
  cancelPublicBookingBySlug,
  createPublicBookingReviewBySlug,
  getPublicBookingReviewBySlug,
  getPublicSalon,
  getPublicServiceAvailability,
  getPublicServiceStaff,
  mapServiceAvailabilityToSelectedSlots,
  reschedulePublicBookingBySlug,
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
  ServiceStaffList,
  type ServiceStaffListState,
} from '../components/ServiceStaffList'
import type { ManageBookingSnapshot } from '../types/publicBooking'
import type { PublicSelectedSlot } from '../types/publicSalon'
import { ANY_STAFF_CHOICE_ID } from '../types/publicSalon'
import { defaultDateInTimeZone } from '../utils/date'
import { formatBookingDateTime } from '../utils/formatTime'
import {
  loadManageSnapshot,
  persistManageSnapshot,
  stripManageTokenFromUrl,
} from '../utils/manageBookingStorage'
import {
  isManageSlotConflictError,
  mapPublicManageBookingError,
} from '../utils/mapPublicManageBookingError'
import { mapPublicReviewError } from '../utils/mapPublicReviewError'
import type { PublicBookingReviewStatusResponse } from '../types/reviews'

type ManageView =
  | 'summary'
  | 'cancel_confirm'
  | 'reschedule_staff'
  | 'reschedule_date'
  | 'reschedule_time'
  | 'review'

type ReviewLoadState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'none' }
  | { status: 'exists'; review: PublicBookingReviewStatusResponse }
  | { status: 'error'; message: string }

type StaffChoice =
  | { kind: 'any' }
  | { kind: 'specific'; staffId: string }

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
  fallback: string,
): string {
  if (staffState.status === 'success') {
    const member = staffState.staff.find((s) => s.id === staffId)
    if (member) {
      return member.display_name
    }
  }
  return fallback || 'Мастер'
}

function mergeSnapshotToken(
  slug: string,
  bookingId: string,
  token: string,
): ManageBookingSnapshot {
  const existing = loadManageSnapshot(slug, bookingId)
  if (existing) {
    return persistManageSnapshot({ ...existing, token })
  }
  return persistManageSnapshot({
    token,
    booking_id: bookingId,
    slug,
    salon_id: '',
    service_id: '',
    staff_id: '',
    service_name: '',
    staff_display_name: '',
    service_start: '',
    service_end: '',
    hold_expires_at: '',
  })
}

export function PublicManageBookingPage() {
  const { slug, bookingId } = useParams<{ slug: string; bookingId: string }>()
  const [searchParams] = useSearchParams()
  const [snapshot, setSnapshot] = useState<ManageBookingSnapshot | null>(null)
  const [accessChecked, setAccessChecked] = useState(false)
  const [salonName, setSalonName] = useState<string | null>(null)
  const [salonLogoUrl, setSalonLogoUrl] = useState<string | null>(null)
  const [salonTimeZone, setSalonTimeZone] = useState('UTC')
  const [salonLoadError, setSalonLoadError] = useState<string | null>(null)
  const [view, setView] = useState<ManageView>('summary')
  const [cancelReason, setCancelReason] = useState('')
  const [actionError, setActionError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const submitInFlightRef = useRef(false)

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
  const [reviewLoadState, setReviewLoadState] = useState<ReviewLoadState>({
    status: 'idle',
  })
  const [reviewRating, setReviewRating] = useState(5)
  const [reviewTitle, setReviewTitle] = useState('')
  const [reviewBody, setReviewBody] = useState('')
  const [reviewSuccess, setReviewSuccess] = useState(false)

  useEffect(() => {
    if (!slug || !bookingId) {
      setAccessChecked(true)
      return
    }

    const queryToken = searchParams.get('token')?.trim()
    if (queryToken) {
      const merged = mergeSnapshotToken(slug, bookingId, queryToken)
      setSnapshot(merged)
      stripManageTokenFromUrl()
    } else {
      setSnapshot(loadManageSnapshot(slug, bookingId))
    }
    setAccessChecked(true)
  }, [slug, bookingId, searchParams])

  useEffect(() => {
    if (!slug || !accessChecked) {
      return
    }

    let cancelled = false
    getPublicSalon(slug)
      .then((salon) => {
        if (cancelled) return
        setSalonName(salon.name)
        setSalonLogoUrl(salon.logo_url)
        setSalonTimeZone(salon.timezone)
        setSalonLoadError(null)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const message =
          err instanceof ApiError ? err.message : 'Something went wrong'
        setSalonLoadError(message)
      })

    return () => {
      cancelled = true
    }
  }, [slug, accessChecked])

  useEffect(() => {
    if (!slug || !bookingId || !snapshot?.token) {
      setReviewLoadState({ status: 'idle' })
      return
    }

    let cancelled = false
    setReviewLoadState({ status: 'loading' })

    getPublicBookingReviewBySlug(slug, bookingId, snapshot.token)
      .then((review) => {
        if (!cancelled) {
          setReviewLoadState({ status: 'exists', review })
        }
      })
      .catch((err: unknown) => {
        if (cancelled) {
          return
        }
        if (err instanceof ApiError && err.status === 404) {
          setReviewLoadState({ status: 'none' })
          return
        }
        const message =
          err instanceof ApiError ? err.message : 'Не удалось проверить отзыв'
        setReviewLoadState({ status: 'error', message })
      })

    return () => {
      cancelled = true
    }
  }, [slug, bookingId, snapshot?.token])

  useEffect(() => {
    if (
      !slug ||
      !snapshot?.service_id ||
      view !== 'reschedule_staff' &&
        view !== 'reschedule_date' &&
        view !== 'reschedule_time'
    ) {
      if (view === 'summary' || view === 'cancel_confirm') {
        setStaffState({ status: 'idle' })
      }
      return
    }

    let cancelled = false
    setStaffState({ status: 'loading' })

    getPublicServiceStaff(slug, snapshot.service_id)
      .then((result) => {
        if (!cancelled) {
          setStaffState({ status: 'success', staff: result.staff })
        }
      })
      .catch(() => {
        if (!cancelled) {
          setStaffState({ status: 'error', message: 'Не удалось загрузить мастеров' })
        }
      })

    return () => {
      cancelled = true
    }
  }, [slug, snapshot?.service_id, view])

  useEffect(() => {
    if (
      !slug ||
      !snapshot?.service_id ||
      staffChoice === null ||
      selectedDate === null ||
      view !== 'reschedule_time'
    ) {
      if (view !== 'reschedule_time') {
        setAvailabilityState({ status: 'idle' })
      }
      return
    }

    let cancelled = false
    setAvailabilityState({ status: 'loading' })

    const staffIdForQuery =
      staffChoice.kind === 'specific' ? staffChoice.staffId : undefined

    getPublicServiceAvailability(slug, {
      serviceId: snapshot.service_id,
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
    snapshot?.service_id,
    staffChoice,
    selectedDate,
    view,
    availabilityNonce,
  ])

  const refreshSnapshot = useCallback((next: ManageBookingSnapshot) => {
    persistManageSnapshot(next)
    setSnapshot(next)
  }, [])

  const handleStartReview = useCallback(() => {
    setActionError(null)
    setReviewSuccess(false)
    setView('review')
  }, [])

  const handleReviewBack = useCallback(() => {
    setActionError(null)
    setView('summary')
  }, [])

  const handleSubmitReview = useCallback(async () => {
    if (!slug || !bookingId || !snapshot?.token || submitInFlightRef.current) {
      return
    }
    if (reviewRating < 1 || reviewRating > 5) {
      setActionError('Выберите оценку от 1 до 5.')
      return
    }

    submitInFlightRef.current = true
    setSubmitting(true)
    setActionError(null)

    try {
      const result = await createPublicBookingReviewBySlug(slug, bookingId, {
        token: snapshot.token,
        rating: reviewRating,
        title: reviewTitle.trim() || undefined,
        body: reviewBody.trim() || undefined,
      })
      setReviewLoadState({
        status: 'exists',
        review: {
          review_id: result.review_id,
          booking_id: result.booking_id,
          status: result.status,
          rating: result.rating,
          title: result.title,
          body: result.body,
          created_at: result.created_at,
        },
      })
      setReviewSuccess(true)
      setView('summary')
    } catch (err: unknown) {
      setActionError(mapPublicReviewError(err))
    } finally {
      setSubmitting(false)
      submitInFlightRef.current = false
    }
  }, [
    slug,
    bookingId,
    snapshot?.token,
    reviewRating,
    reviewTitle,
    reviewBody,
  ])

  const handleStartCancel = useCallback(() => {
    setActionError(null)
    setView('cancel_confirm')
  }, [])

  const handleCancelBack = useCallback(() => {
    setActionError(null)
    setCancelReason('')
    setView('summary')
  }, [])

  const handleConfirmCancel = useCallback(async () => {
    if (!slug || !bookingId || !snapshot || submitInFlightRef.current) {
      return
    }
    if (snapshot.status === 'cancelled') {
      return
    }

    submitInFlightRef.current = true
    setSubmitting(true)
    setActionError(null)

    try {
      const result = await cancelPublicBookingBySlug(slug, bookingId, {
        token: snapshot.token,
        reason: cancelReason.trim() || undefined,
      })
      refreshSnapshot({
        ...snapshot,
        status: result.status,
        cancelled_at: result.cancelled_at,
        token: '',
      })
      setView('summary')
      setCancelReason('')
    } catch (err: unknown) {
      setActionError(mapPublicManageBookingError(err))
    } finally {
      setSubmitting(false)
      submitInFlightRef.current = false
    }
  }, [slug, bookingId, snapshot, cancelReason, refreshSnapshot])

  const handleStartReschedule = useCallback(() => {
    if (!snapshot?.service_id) {
      setActionError(
        'Перенос недоступен: откройте полную ссылку управления или создайте запись заново.',
      )
      return
    }
    setActionError(null)
    setStaffChoice(null)
    setSelectedDate(null)
    setSelectedSlot(null)
    setAvailabilityNonce(0)
    setView('reschedule_staff')
  }, [snapshot?.service_id])

  const handleSelectStaff = useCallback(
    (staffId: string) => {
      setStaffChoice({ kind: 'specific', staffId })
      setSelectedSlot(null)
      setSelectedDate(defaultDateInTimeZone(salonTimeZone))
      setActionError(null)
      setView('reschedule_date')
    },
    [salonTimeZone],
  )

  const handleSelectAnyStaff = useCallback(() => {
    setStaffChoice({ kind: 'any' })
    setSelectedSlot(null)
    setSelectedDate(defaultDateInTimeZone(salonTimeZone))
    setActionError(null)
    setView('reschedule_date')
  }, [salonTimeZone])

  const handleSelectDate = useCallback((isoDate: string) => {
    setSelectedDate(isoDate)
    setSelectedSlot(null)
    setActionError(null)
    setView('reschedule_time')
  }, [])

  const handleSelectSlot = useCallback((slot: PublicSelectedSlot) => {
    setSelectedSlot(slot)
    setActionError(null)
  }, [])

  const handleConfirmReschedule = useCallback(async () => {
    if (
      !slug ||
      !bookingId ||
      !snapshot ||
      !selectedSlot ||
      submitInFlightRef.current
    ) {
      return
    }
    if (!snapshot.token) {
      setActionError('Ссылка управления недействительна.')
      return
    }

    submitInFlightRef.current = true
    setSubmitting(true)
    setActionError(null)

    try {
      const result = await reschedulePublicBookingBySlug(slug, bookingId, {
        token: snapshot.token,
        staff_id: selectedSlot.staff_id,
        service_start: selectedSlot.service_start,
      })
      const staffLabel = resolveStaffDisplayName(
        staffState,
        result.staff_id,
        snapshot.staff_display_name,
      )
      refreshSnapshot({
        ...snapshot,
        staff_id: result.staff_id,
        staff_display_name: staffLabel,
        service_start: result.service_start,
        service_end: result.service_end,
        status: result.status,
      })
      setView('summary')
      setStaffChoice(null)
      setSelectedDate(null)
      setSelectedSlot(null)
    } catch (err: unknown) {
      setActionError(mapPublicManageBookingError(err))
      if (isManageSlotConflictError(err)) {
        setSelectedSlot(null)
        setAvailabilityNonce((n) => n + 1)
        setView('reschedule_time')
      }
    } finally {
      setSubmitting(false)
      submitInFlightRef.current = false
    }
  }, [
    slug,
    bookingId,
    snapshot,
    selectedSlot,
    staffState,
    refreshSnapshot,
  ])

  if (!accessChecked) {
    return (
      <main className="page">
        <LoadingState message="Загрузка…" />
      </main>
    )
  }

  if (!slug || !bookingId) {
    return (
      <main className="page">
        <ErrorState
          title="Неверная ссылка"
          message="Проверьте адрес страницы управления записью."
        />
      </main>
    )
  }

  const hasToken = Boolean(snapshot?.token)
  const isCancelled =
    snapshot?.status === 'cancelled' || Boolean(snapshot?.cancelled_at)

  if (!snapshot || (!hasToken && !isCancelled)) {
    return (
      <main className="page public-manage-page">
        <ErrorState
          title="Ссылка недействительна"
          message="Откройте страницу из подтверждения записи или используйте сохранённую ссылку с доступом."
        />
        <p className="public-manage-page__back">
          <Link to={`/s/${encodeURIComponent(slug)}`}>Вернуться в салон</Link>
        </p>
      </main>
    )
  }

  const canReschedule =
    hasToken && !isCancelled && Boolean(snapshot.service_id.trim())
  const canReview =
    hasToken &&
    !isCancelled &&
    reviewLoadState.status !== 'loading' &&
    reviewLoadState.status !== 'exists'
  const staffListSelectedId = staffChoiceToSelectedId(staffChoice)

  return (
    <main className="page public-manage-page">
      {salonName ? (
        <SalonHeader name={salonName} logoUrl={salonLogoUrl} />
      ) : salonLoadError ? (
        <p className="public-manage-page__salon-hint" role="status">
          {salonLoadError}
        </p>
      ) : null}

      <section className="public-manage-page__panel" aria-label="Управление записью">
        <h1 className="public-manage-page__title">Ваша запись</h1>

        {isCancelled ? (
          <p className="public-manage-page__status public-manage-page__status--cancelled">
            Запись отменена
            {snapshot.cancelled_at
              ? ` · ${formatBookingDateTime(snapshot.cancelled_at, salonTimeZone)}`
              : null}
          </p>
        ) : snapshot.status ? (
          <p className="public-manage-page__status">Статус: {snapshot.status}</p>
        ) : null}

        <dl className="booking-summary__list public-manage-page__details">
          {snapshot.service_name ? (
            <div className="booking-summary__row">
              <dt>Услуга</dt>
              <dd>{snapshot.service_name}</dd>
            </div>
          ) : null}
          {snapshot.staff_display_name ? (
            <div className="booking-summary__row">
              <dt>Мастер</dt>
              <dd>{snapshot.staff_display_name}</dd>
            </div>
          ) : null}
          {snapshot.service_start ? (
            <div className="booking-summary__row">
              <dt>Начало</dt>
              <dd>{formatBookingDateTime(snapshot.service_start, salonTimeZone)}</dd>
            </div>
          ) : null}
          {snapshot.service_end ? (
            <div className="booking-summary__row">
              <dt>Окончание</dt>
              <dd>{formatBookingDateTime(snapshot.service_end, salonTimeZone)}</dd>
            </div>
          ) : null}
          <div className="booking-summary__row">
            <dt>Номер записи</dt>
            <dd className="booking-confirmation__booking-id">
              {snapshot.booking_id}
            </dd>
          </div>
        </dl>

        {actionError && view === 'summary' ? (
          <div className="form-error-banner" role="alert">
            <p>{actionError}</p>
          </div>
        ) : null}

        {reviewLoadState.status === 'exists' ? (
          <p className="public-manage-page__status" role="status">
            Спасибо! Ваш отзыв отправлен (статус: {reviewLoadState.review.status}
            ).
          </p>
        ) : null}

        {reviewSuccess ? (
          <p className="public-manage-page__status" role="status">
            Отзыв принят и ожидает модерации.
          </p>
        ) : null}

        {view === 'summary' && !isCancelled && hasToken ? (
          <div className="public-manage-page__actions">
            {canReview ? (
              <button
                type="button"
                className="btn btn--primary btn--block"
                onClick={handleStartReview}
              >
                Оставить отзыв
              </button>
            ) : null}
            <button
              type="button"
              className="btn btn--secondary btn--block"
              onClick={handleStartReschedule}
              disabled={!canReschedule}
            >
              Перенести запись
            </button>
            <button
              type="button"
              className="btn btn--secondary btn--block"
              onClick={handleStartCancel}
            >
              Отменить запись
            </button>
          </div>
        ) : null}

        {view === 'review' ? (
          <div className="public-manage-page__subflow">
            <h2 className="booking-step__heading">Отзыв о визите</h2>
            <label className="public-manage-page__field">
              <span className="public-manage-page__label">Оценка</span>
              <select
                className="form-field__input"
                value={reviewRating}
                disabled={submitting}
                onChange={(e) => setReviewRating(Number(e.target.value))}
              >
                {[5, 4, 3, 2, 1].map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <label className="public-manage-page__field">
              <span className="public-manage-page__label">
                Заголовок (необязательно)
              </span>
              <input
                className="form-field__input"
                type="text"
                maxLength={200}
                value={reviewTitle}
                disabled={submitting}
                onChange={(e) => setReviewTitle(e.target.value)}
              />
            </label>
            <label className="public-manage-page__field">
              <span className="public-manage-page__label">
                Комментарий (необязательно)
              </span>
              <textarea
                className="public-manage-page__textarea"
                rows={4}
                value={reviewBody}
                disabled={submitting}
                onChange={(e) => setReviewBody(e.target.value)}
              />
            </label>
            {actionError ? (
              <div className="form-error-banner" role="alert">
                <p>{actionError}</p>
              </div>
            ) : null}
            <div className="booking-step__actions">
              <button
                type="button"
                className="btn btn--secondary"
                disabled={submitting}
                onClick={handleReviewBack}
              >
                Назад
              </button>
              <button
                type="button"
                className="btn btn--primary"
                disabled={submitting}
                onClick={() => void handleSubmitReview()}
              >
                {submitting ? 'Отправка…' : 'Отправить отзыв'}
              </button>
            </div>
          </div>
        ) : null}

        {view === 'cancel_confirm' ? (
          <div className="public-manage-page__subflow">
            <h2 className="booking-step__heading">Отмена записи</h2>
            <p className="public-manage-page__lead">
              Вы уверены, что хотите отменить запись?
            </p>
            <label className="public-manage-page__field">
              <span className="public-manage-page__label">
                Причина (необязательно)
              </span>
              <textarea
                className="public-manage-page__textarea"
                value={cancelReason}
                maxLength={255}
                rows={3}
                disabled={submitting}
                onChange={(e) => setCancelReason(e.target.value)}
              />
            </label>
            {actionError ? (
              <div className="form-error-banner" role="alert">
                <p>{actionError}</p>
              </div>
            ) : null}
            <div className="booking-step__actions">
              <button
                type="button"
                className="btn btn--secondary"
                disabled={submitting}
                onClick={handleCancelBack}
              >
                Назад
              </button>
              <button
                type="button"
                className="btn btn--primary"
                disabled={submitting}
                onClick={() => void handleConfirmCancel()}
              >
                {submitting ? 'Отмена…' : 'Подтвердить отмену'}
              </button>
            </div>
          </div>
        ) : null}

        {view === 'reschedule_staff' ? (
          <div className="public-manage-page__subflow">
            <h2 className="booking-step__heading">Выберите мастера</h2>
            {actionError ? (
              <div className="form-error-banner" role="alert">
                <p>{actionError}</p>
              </div>
            ) : null}
            <ServiceStaffList
              state={staffState}
              selectedStaffId={staffListSelectedId}
              onSelectStaff={(member) => handleSelectStaff(member.id)}
              onSelectAnyStaff={handleSelectAnyStaff}
            />
            <div className="booking-step__actions">
              <button
                type="button"
                className="btn btn--secondary"
                onClick={() => {
                  setActionError(null)
                  setView('summary')
                }}
              >
                Назад
              </button>
            </div>
          </div>
        ) : null}

        {view === 'reschedule_date' && staffChoice !== null ? (
          <div className="public-manage-page__subflow">
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
                onClick={() => setView('reschedule_staff')}
              >
                К выбору мастера
              </button>
            </div>
          </div>
        ) : null}

        {view === 'reschedule_time' &&
        staffChoice !== null &&
        selectedDate !== null ? (
          <div className="public-manage-page__subflow">
            <h2 className="booking-step__heading">Выберите время</h2>
            {actionError ? (
              <div className="form-error-banner" role="alert">
                <p>{actionError}</p>
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
                disabled={submitting}
                onClick={() => setView('reschedule_date')}
              >
                К выбору даты
              </button>
              <button
                type="button"
                className="btn btn--primary"
                disabled={selectedSlot === null || submitting}
                onClick={() => void handleConfirmReschedule()}
              >
                {submitting ? 'Сохранение…' : 'Подтвердить перенос'}
              </button>
            </div>
          </div>
        ) : null}

        <p className="public-manage-page__back">
          <Link to={`/s/${encodeURIComponent(slug)}`}>Вернуться в салон</Link>
        </p>
      </section>
    </main>
  )
}
