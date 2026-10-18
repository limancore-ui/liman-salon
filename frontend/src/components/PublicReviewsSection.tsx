import { useEffect, useState } from 'react'
import { getPublicReviews } from '../api/publicSalon'
import { t } from '../i18n'
import type { PublicSalonReview } from '../types/reviews'

type PublicReviewsSectionProps = {
  slug: string
  timeZone: string
}

type PublicReviewsState =
  | { requestKey: string; status: 'loading' }
  | { requestKey: string; status: 'success'; reviews: PublicSalonReview[] }
  | { requestKey: string; status: 'error' }

function formatPublishedDate(value: string, timeZone: string): string {
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) {
    return ''
  }

  try {
    return new Intl.DateTimeFormat('ru-RU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      timeZone,
    }).format(date)
  } catch {
    return new Intl.DateTimeFormat('ru-RU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      timeZone: 'UTC',
    }).format(date)
  }
}

function ReviewCard({
  review,
  timeZone,
}: {
  review: PublicSalonReview
  timeZone: string
}) {
  const rating = Math.max(0, Math.min(5, Math.floor(review.rating)))
  const title = review.title?.trim()
  const body = review.body?.trim()
  const staffName = review.staff_display_name?.trim()
  const publishedDate = formatPublishedDate(review.published_at, timeZone)

  return (
    <li className="public-reviews-list__item">
      <article className="public-review-card">
        <div
          className="public-review-card__rating"
          role="img"
          aria-label={t('public.reviews.rating', { rating, max: 5 })}
        >
          <span aria-hidden="true">
            {Array.from({ length: 5 }, (_, index) =>
              index < rating ? '★' : '☆',
            ).join('')}
          </span>
        </div>
        {title ? <h3 className="public-review-card__title">{title}</h3> : null}
        {body ? <p className="public-review-card__body">{review.body}</p> : null}
        <div className="public-review-card__meta">
          {staffName ? (
            <p>{t('public.reviews.staff', { name: staffName })}</p>
          ) : null}
          {publishedDate ? (
            <time dateTime={review.published_at}>{publishedDate}</time>
          ) : null}
        </div>
      </article>
    </li>
  )
}

export function PublicReviewsSection({
  slug,
  timeZone,
}: PublicReviewsSectionProps) {
  const [retryCount, setRetryCount] = useState(0)
  const [state, setState] = useState<PublicReviewsState>({
    requestKey: '',
    status: 'loading',
  })
  const requestKey = `${slug}:${retryCount}`

  useEffect(() => {
    let currentRequest = true
    const controller = new AbortController()

    getPublicReviews(slug, controller.signal)
      .then((response) => {
        if (currentRequest) {
          setState({
            requestKey,
            status: 'success',
            reviews: response.reviews,
          })
        }
      })
      .catch((error: unknown) => {
        if (
          !currentRequest ||
          (error instanceof DOMException && error.name === 'AbortError')
        ) {
          return
        }
        setState({ requestKey, status: 'error' })
      })

    return () => {
      currentRequest = false
      controller.abort()
    }
  }, [slug, retryCount, requestKey])

  const visibleState: PublicReviewsState =
    state.requestKey === requestKey
      ? state
      : { requestKey, status: 'loading' }

  return (
    <section
      className="public-reviews-section"
      aria-labelledby="public-reviews-section-title"
    >
      <div className="public-reviews-section__heading">
        <h2
          id="public-reviews-section-title"
          className="public-reviews-section__title"
        >
          {t('public.reviews.title')}
        </h2>
      </div>

      {visibleState.status === 'loading' ? (
        <p className="public-reviews-state" role="status" aria-live="polite">
          {t('public.reviews.loading')}
        </p>
      ) : visibleState.status === 'error' ? (
        <div className="public-reviews-state public-reviews-state--error" role="alert">
          <p>{t('public.reviews.loadError')}</p>
          <button
            type="button"
            className="public-reviews-state__retry"
            onClick={() => setRetryCount((count) => count + 1)}
          >
            {t('common.retry')}
          </button>
        </div>
      ) : visibleState.reviews.length === 0 ? (
        <p className="public-reviews-state" role="status">
          {t('public.reviews.empty')}
        </p>
      ) : (
        <ul className="public-reviews-list">
          {visibleState.reviews.map((review) => (
            <ReviewCard key={review.id} review={review} timeZone={timeZone} />
          ))}
        </ul>
      )}
    </section>
  )
}
