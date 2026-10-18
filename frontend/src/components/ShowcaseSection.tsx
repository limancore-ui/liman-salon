import { useEffect, useState } from 'react'
import { getPublicShowcase } from '../api/publicSalon'
import { t } from '../i18n'
import type {
  PublicShowcaseCategory,
  PublicShowcaseItem,
} from '../types/publicShowcase'
import { formatPrice } from '../utils/format'

type ShowcaseSectionProps = {
  slug: string
  currencyCode: string
}

type ShowcaseState =
  | { requestKey: string; status: 'loading' }
  | { requestKey: string; status: 'success'; items: PublicShowcaseItem[] }
  | { requestKey: string; status: 'error' }

const CATEGORY_OPTIONS: Array<{
  value: PublicShowcaseCategory | null
  label: Parameters<typeof t>[0]
}> = [
  { value: null, label: 'public.showcase.all' },
  { value: 'work', label: 'public.showcase.work' },
  { value: 'cosmetics', label: 'public.showcase.cosmetics' },
  { value: 'dyes', label: 'public.showcase.dyes' },
  { value: 'varnishes', label: 'public.showcase.varnishes' },
]

function categoryLabel(category: PublicShowcaseCategory): string {
  const option = CATEGORY_OPTIONS.find((candidate) => candidate.value === category)
  return option ? t(option.label) : ''
}

function ShowcaseCard({
  item,
  currencyCode,
}: {
  item: PublicShowcaseItem
  currencyCode: string
}) {
  const [imageFailed, setImageFailed] = useState(false)
  const description = item.description?.trim()
  const price =
    item.price_cents !== null && item.price_cents > 0
      ? formatPrice(item.price_cents, currencyCode)
      : null

  return (
    <li className="showcase-grid__item">
      <article className="showcase-card">
        <div className="showcase-card__image-frame">
          {imageFailed ? (
            <div
              className="showcase-card__image-fallback"
              role="img"
              aria-label={t('public.showcase.imageUnavailable')}
            >
              <span aria-hidden="true">◇</span>
              <span>{t('public.showcase.imageUnavailable')}</span>
            </div>
          ) : (
            <img
              className="showcase-card__image"
              src={item.image_url}
              alt={item.title}
              loading="lazy"
              onError={() => setImageFailed(true)}
            />
          )}
        </div>
        <div className="showcase-card__body">
          <p className="showcase-card__category">{categoryLabel(item.category)}</p>
          <h3 className="showcase-card__title">{item.title}</h3>
          {description ? (
            <p className="showcase-card__description">{description}</p>
          ) : null}
          {price ? <p className="showcase-card__price">{price}</p> : null}
        </div>
      </article>
    </li>
  )
}

export function ShowcaseSection({ slug, currencyCode }: ShowcaseSectionProps) {
  const [category, setCategory] = useState<PublicShowcaseCategory | null>(null)
  const [retryCount, setRetryCount] = useState(0)
  const [state, setState] = useState<ShowcaseState>({
    requestKey: '',
    status: 'loading',
  })
  const requestKey = `${slug}:${category ?? 'all'}:${retryCount}`

  useEffect(() => {
    let currentRequest = true
    const controller = new AbortController()

    getPublicShowcase(slug, category ?? undefined, controller.signal)
      .then((response) => {
        if (currentRequest) {
          setState({ requestKey, status: 'success', items: response.items })
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
  }, [slug, category, retryCount, requestKey])

  const visibleState: ShowcaseState =
    state.requestKey === requestKey
      ? state
      : { requestKey, status: 'loading' }

  return (
    <section
      className="showcase-section"
      aria-labelledby="showcase-section-title"
    >
      <div className="showcase-section__heading">
        <h2 id="showcase-section-title" className="showcase-section__title">
          {t('public.showcase.title')}
        </h2>
        <p className="showcase-section__subtitle">
          {t('public.showcase.subtitle')}
        </p>
      </div>

      <div
        className="showcase-filter"
        role="group"
        aria-label={t('public.showcase.categories')}
      >
        {CATEGORY_OPTIONS.map((option) => (
          <button
            key={option.label}
            type="button"
            className="showcase-filter__button"
            aria-pressed={category === option.value}
            onClick={() => setCategory(option.value)}
          >
            {t(option.label)}
          </button>
        ))}
      </div>

      {visibleState.status === 'loading' ? (
        <p className="showcase-state" role="status" aria-live="polite">
          {t('public.showcase.loading')}
        </p>
      ) : visibleState.status === 'error' ? (
        <div className="showcase-state showcase-state--error" role="alert">
          <p>{t('public.showcase.loadError')}</p>
          <button
            type="button"
            className="showcase-state__retry"
            onClick={() => setRetryCount((count) => count + 1)}
          >
            {t('common.retry')}
          </button>
        </div>
      ) : visibleState.items.length === 0 ? (
        <p className="showcase-state" role="status">
          {t('public.showcase.empty')}
        </p>
      ) : (
        <ul className="showcase-grid">
          {visibleState.items.map((item) => (
            <ShowcaseCard
              key={item.id}
              item={item}
              currencyCode={currencyCode}
            />
          ))}
        </ul>
      )}
    </section>
  )
}
