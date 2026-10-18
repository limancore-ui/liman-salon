import { useCallback, useEffect, useState } from 'react'
import { AdminLayout } from '../components/AdminLayout'
import { useAuth } from '../auth/AuthContext'
import {
  fetchAdminReviews,
  hideAdminReview,
  publishAdminReview,
  rejectAdminReview,
} from '../api/reviews'
import { isUnauthorizedError } from '../api/auth'
import type { AdminReviewListItem } from '../types/reviews'
import { t, reviewStatusLabel } from '../i18n'
import { adminUserErrorMessage } from '../utils/adminUserError'

export function AdminReviewsPage() {
  const { session, clearAuthAndRedirect } = useAuth()
  const [items, setItems] = useState<AdminReviewListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actingId, setActingId] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!session) {
      return
    }
    setLoading(true)
    setError(null)
    try {
      const rows = await fetchAdminReviews(session.token, session.salon.salon_id)
      setItems(rows)
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      setError(adminUserErrorMessage(err, 'admin.reviews.loadFailed'))
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [session, clearAuthAndRedirect])

  useEffect(() => {
    void load()
  }, [load])

  async function runAction(
    reviewId: string,
    action: 'publish' | 'reject' | 'hide',
  ) {
    if (!session) {
      return
    }
    setActingId(reviewId)
    setError(null)
    try {
      if (action === 'publish') {
        await publishAdminReview(session.token, session.salon.salon_id, reviewId)
      } else if (action === 'reject') {
        await rejectAdminReview(session.token, session.salon.salon_id, reviewId)
      } else {
        await hideAdminReview(session.token, session.salon.salon_id, reviewId)
      }
      await load()
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      setError(adminUserErrorMessage(err, 'admin.reviews.actionFailed'))
    } finally {
      setActingId(null)
    }
  }

  return (
    <AdminLayout>
      <section className="admin-customers">
        <header className="admin-customers__header">
          <h1 className="admin-customers__title">{t('admin.reviews.title')}</h1>
          <p className="admin-customers__lead">{t('admin.reviews.lead')}</p>
        </header>

        {loading ? (
          <p className="admin-customers__state" role="status">
            {t('admin.reviews.loading')}
          </p>
        ) : null}

        {!loading && error ? (
          <p className="admin-customers__state admin-customers__state--error" role="alert">
            {error}
          </p>
        ) : null}

        {!loading && !error && items.length === 0 ? (
          <p className="admin-customers__state">{t('admin.reviews.empty')}</p>
        ) : null}

        {!loading && items.length > 0 ? (
          <ul className="admin-customers__list">
            {items.map((row) => (
              <li key={row.id} className="admin-customers__row">
                <div>
                  <strong>
                    {row.rating}/5 · {reviewStatusLabel(row.status)}
                  </strong>
                  <p>
                    {row.customer_display_name}
                    {row.staff_display_name ? ` · ${row.staff_display_name}` : null}
                  </p>
                  {row.title ? <p>{row.title}</p> : null}
                  {row.body ? <p>{row.body}</p> : null}
                </div>
                <div className="admin-customers__row-actions">
                  {row.status === 'pending' ? (
                    <>
                      <button
                        type="button"
                        className="btn btn--secondary btn--compact"
                        disabled={actingId === row.id}
                        onClick={() => void runAction(row.id, 'publish')}
                      >
                        {t('admin.reviews.publish')}
                      </button>
                      <button
                        type="button"
                        className="btn btn--secondary btn--compact"
                        disabled={actingId === row.id}
                        onClick={() => void runAction(row.id, 'reject')}
                      >
                        {t('admin.reviews.reject')}
                      </button>
                    </>
                  ) : null}
                  {row.status === 'published' ? (
                    <button
                      type="button"
                      className="btn btn--secondary btn--compact"
                      disabled={actingId === row.id}
                      onClick={() => void runAction(row.id, 'hide')}
                    >
                      {t('admin.reviews.hide')}
                    </button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </AdminLayout>
  )
}
