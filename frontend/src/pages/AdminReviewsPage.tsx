import { useCallback, useEffect, useState } from 'react'
import { AdminLayout } from '../components/AdminLayout'
import { useAuth } from '../auth/AuthContext'
import {
  fetchAdminReviews,
  hideAdminReview,
  publishAdminReview,
  rejectAdminReview,
} from '../api/reviews'
import { ApiError } from '../api/errors'
import { isUnauthorizedError } from '../api/auth'
import type { AdminReviewListItem } from '../types/reviews'

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
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError('Could not load reviews.')
      }
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
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError('Action failed.')
      }
    } finally {
      setActingId(null)
    }
  }

  return (
    <AdminLayout>
      <section className="admin-customers">
        <header className="admin-customers__header">
          <h1 className="admin-customers__title">Reviews</h1>
          <p className="admin-customers__lead">Moderate customer feedback.</p>
        </header>

        {loading ? (
          <p className="admin-customers__state" role="status">
            Loading reviews…
          </p>
        ) : null}

        {!loading && error ? (
          <p className="admin-customers__state admin-customers__state--error" role="alert">
            {error}
          </p>
        ) : null}

        {!loading && !error && items.length === 0 ? (
          <p className="admin-customers__state">No reviews yet.</p>
        ) : null}

        {!loading && items.length > 0 ? (
          <ul className="admin-customers__list">
            {items.map((row) => (
              <li key={row.id} className="admin-customers__row">
                <div>
                  <strong>
                    {row.rating}/5 · {row.status}
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
                        Publish
                      </button>
                      <button
                        type="button"
                        className="btn btn--secondary btn--compact"
                        disabled={actingId === row.id}
                        onClick={() => void runAction(row.id, 'reject')}
                      >
                        Reject
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
                      Hide
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
