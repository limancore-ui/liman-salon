"""PostgreSQL integration for review lifecycle (C18)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.deps import get_as_of, get_db
from app.db.models.booking import Booking
from app.db.models.customer import Customer
from app.db.models.review import Review
from app.db.models.salon import Salon
from app.db.models.service import Service
from app.db.models.staff import Staff
from app.db.models.staff_service import StaffService
from app.db.models.user import User
from app.db.models.working_hour import WorkingHour
from app.db.session import engine
from app.main import create_app
from app.services.review.service import ReviewService

UTC = timezone.utc
FIXED_AS_OF = datetime(2026, 8, 1, 8, 0, tzinfo=UTC)
MOD_AS_OF = datetime(2026, 8, 2, 10, 0, tzinfo=UTC)


def _postgres_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_available(),
    reason="PostgreSQL test database not reachable",
)


@pytest.fixture
def db_session() -> Session:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def public_client(db_session: Session) -> TestClient:
    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()
        app.dependency_overrides.clear()


def _seed_bookable_salon(session: Session) -> tuple[Salon, Staff, Service]:
    suffix = uuid.uuid4().hex[:8]
    salon = Salon(
        name=f"Review E2E {suffix}",
        slug=f"review-e2e-{suffix}",
        timezone="UTC",
        currency_code="KZT",
        is_active=True,
    )
    session.add(salon)
    session.flush()

    for day in range(0, 7):
        session.add(
            WorkingHour(
                salon_id=salon.id,
                staff_id=None,
                day_of_week=day,
                start_time=time(0, 0),
                end_time=time(23, 59),
            )
        )

    staff = Staff(
        salon_id=salon.id,
        display_name="Stylist",
        is_active=True,
        is_bookable=True,
        sort_order=1,
    )
    service = Service(
        salon_id=salon.id,
        name="Cut",
        duration_minutes=60,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
        price_cents=1000,
        is_active=True,
        sort_order=1,
    )
    session.add_all([staff, service])
    session.flush()
    session.add(
        StaffService(
            salon_id=salon.id,
            staff_id=staff.id,
            service_id=service.id,
        )
    )
    session.flush()
    return salon, staff, service


def _seed_moderator(session: Session) -> User:
    user = User(
        email=f"mod-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Moderator",
        password_hash="hash",
        is_active=True,
    )
    session.add(user)
    session.flush()
    return user


def _availability_params(*, service_id: uuid.UUID, staff_id: uuid.UUID, day: date) -> dict[str, str]:
    day_str = day.isoformat()
    return {
        "service_id": str(service_id),
        "start_date": day_str,
        "end_date": day_str,
        "staff_id": str(staff_id),
    }


def _first_slot(body: dict, staff_id: uuid.UUID) -> dict[str, str]:
    staff_key = str(staff_id)
    for row in body["staff"]:
        if row["staff_id"] == staff_key and row["slots"]:
            return row["slots"][0]
    raise AssertionError("no slots")


def _create_public_booking(
    client: TestClient,
    *,
    base: str,
    service_id: uuid.UUID,
    staff_id: uuid.UUID,
    service_start: str,
) -> tuple[uuid.UUID, str]:
    phone = f"+7761{uuid.uuid4().int % 10_000_000:07d}"
    resp = client.post(
        f"{base}/bookings",
        json={
            "full_name": "Review Guest",
            "phone": phone,
            "service_id": str(service_id),
            "staff_id": str(staff_id),
            "service_start": service_start,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    return uuid.UUID(body["booking_id"]), body["manage_token"]


def _complete_booking(session: Session, salon_id: uuid.UUID, booking_id: uuid.UUID) -> Booking:
    row = session.scalar(
        select(Booking).where(Booking.salon_id == salon_id, Booking.id == booking_id)
    )
    assert row is not None
    row.status = "completed"
    row.completed_at = FIXED_AS_OF
    session.flush()
    return row


@pytest.fixture
def bookable_context(
    db_session: Session, public_client: TestClient
) -> tuple[str, Salon, Staff, Service, uuid.UUID, str, Booking]:
    salon, staff, service = _seed_bookable_salon(db_session)
    base = f"/api/v1/public/salons/{salon.slug}"
    probe_day = date(2026, 8, 3)
    avail = public_client.get(
        f"{base}/availability/service",
        params=_availability_params(service_id=service.id, staff_id=staff.id, day=probe_day),
    )
    assert avail.status_code == 200
    slot = _first_slot(avail.json(), staff.id)
    booking_id, token = _create_public_booking(
        public_client,
        base=base,
        service_id=service.id,
        staff_id=staff.id,
        service_start=slot["service_start"],
    )
    booking = _complete_booking(db_session, salon.id, booking_id)
    return base, salon, staff, service, booking_id, token, booking


def test_completed_booking_valid_token_creates_pending_review(
    db_session: Session,
    public_client: TestClient,
    bookable_context: tuple,
) -> None:
    base, salon, _staff, _service, booking_id, token, booking = bookable_context
    resp = public_client.post(
        f"{base}/bookings/{booking_id}/review",
        json={"token": token, "rating": 4, "title": "Good", "body": "Visit"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "pending"
    assert body["rating"] == 4

    review = db_session.scalar(
        select(Review).where(Review.salon_id == salon.id, Review.booking_id == booking_id)
    )
    assert review is not None
    assert review.customer_id == booking.customer_id
    assert review.staff_id == booking.staff_id
    assert review.salon_id == booking.salon_id


@pytest.mark.parametrize(
    "status",
    ["pending", "confirmed", "in_progress", "cancelled", "no_show", "expired"],
)
def test_create_review_rejects_non_completed_status(
    db_session: Session,
    public_client: TestClient,
    status: str,
) -> None:
    salon, staff, service = _seed_bookable_salon(db_session)
    base = f"/api/v1/public/salons/{salon.slug}"
    probe_day = date(2026, 8, 4)
    avail = public_client.get(
        f"{base}/availability/service",
        params=_availability_params(service_id=service.id, staff_id=staff.id, day=probe_day),
    )
    slot = _first_slot(avail.json(), staff.id)
    booking_id, token = _create_public_booking(
        public_client,
        base=base,
        service_id=service.id,
        staff_id=staff.id,
        service_start=slot["service_start"],
    )
    row = db_session.scalar(
        select(Booking).where(Booking.salon_id == salon.id, Booking.id == booking_id)
    )
    assert row is not None
    row.status = status
    db_session.flush()

    resp = public_client.post(
        f"{base}/bookings/{booking_id}/review",
        json={"token": token, "rating": 5},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "validation_error"


def test_create_review_invalid_token_404(
    bookable_context: tuple,
    public_client: TestClient,
) -> None:
    base, _salon, _staff, _service, booking_id, _token, _booking = bookable_context
    resp = public_client.post(
        f"{base}/bookings/{booking_id}/review",
        json={"token": "not-a-valid-token", "rating": 5},
    )
    assert resp.status_code == 404


def test_create_review_wrong_token_for_other_booking(
    db_session: Session,
    public_client: TestClient,
) -> None:
    salon, staff, service = _seed_bookable_salon(db_session)
    base = f"/api/v1/public/salons/{salon.slug}"
    day_a = date(2026, 8, 5)
    avail_a = public_client.get(
        f"{base}/availability/service",
        params=_availability_params(service_id=service.id, staff_id=staff.id, day=day_a),
    )
    slot_a = _first_slot(avail_a.json(), staff.id)
    booking_a, token_a = _create_public_booking(
        public_client,
        base=base,
        service_id=service.id,
        staff_id=staff.id,
        service_start=slot_a["service_start"],
    )
    _complete_booking(db_session, salon.id, booking_a)

    day_b = date(2026, 8, 6)
    avail_b = public_client.get(
        f"{base}/availability/service",
        params=_availability_params(service_id=service.id, staff_id=staff.id, day=day_b),
    )
    slot_b = _first_slot(avail_b.json(), staff.id)
    booking_b, _token_b = _create_public_booking(
        public_client,
        base=base,
        service_id=service.id,
        staff_id=staff.id,
        service_start=slot_b["service_start"],
    )
    _complete_booking(db_session, salon.id, booking_b)

    resp = public_client.post(
        f"{base}/bookings/{booking_b}/review",
        json={"token": token_a, "rating": 5},
    )
    assert resp.status_code == 404


def test_create_review_duplicate_409(
    bookable_context: tuple,
    public_client: TestClient,
) -> None:
    base, _salon, _staff, _service, booking_id, token, _booking = bookable_context
    assert (
        public_client.post(
            f"{base}/bookings/{booking_id}/review",
            json={"token": token, "rating": 5},
        ).status_code
        == 201
    )
    resp = public_client.post(
        f"{base}/bookings/{booking_id}/review",
        json={"token": token, "rating": 4},
    )
    assert resp.status_code == 409


@pytest.mark.parametrize("rating", [0, 6])
def test_create_review_rating_out_of_range(
    bookable_context: tuple,
    public_client: TestClient,
    rating: int,
) -> None:
    base, _salon, _staff, _service, booking_id, token, _booking = bookable_context
    resp = public_client.post(
        f"{base}/bookings/{booking_id}/review",
        json={"token": token, "rating": rating},
    )
    assert resp.status_code == 422


def test_create_review_tenant_isolation_wrong_salon_slug(
    db_session: Session,
    public_client: TestClient,
    bookable_context: tuple,
) -> None:
    _base, salon_a, _staff, _service, booking_id, token, _booking = bookable_context
    salon_b, _, _ = _seed_bookable_salon(db_session)
    base_b = f"/api/v1/public/salons/{salon_b.slug}"
    resp = public_client.post(
        f"{base_b}/bookings/{booking_id}/review",
        json={"token": token, "rating": 5},
    )
    assert resp.status_code == 404
    assert (
        db_session.scalar(
            select(Review).where(Review.salon_id == salon_a.id, Review.booking_id == booking_id)
        )
        is None
    )


def test_moderation_publish_reject_hide_and_metadata(
    db_session: Session,
    public_client: TestClient,
    bookable_context: tuple,
) -> None:
    base, salon, _staff, _service, booking_id, token, _booking = bookable_context
    public_client.post(
        f"{base}/bookings/{booking_id}/review",
        json={"token": token, "rating": 5},
    )
    review = db_session.scalar(
        select(Review).where(Review.salon_id == salon.id, Review.booking_id == booking_id)
    )
    assert review is not None
    moderator = _seed_moderator(db_session)
    svc = ReviewService(db_session)

    rejected_review_row = Review(
        salon_id=salon.id,
        booking_id=None,
        customer_id=review.customer_id,
        staff_id=review.staff_id,
        rating=2,
        status="pending",
    )
    db_session.add(rejected_review_row)
    db_session.flush()
    rejected = svc.reject_review(
        salon_id=salon.id,
        review_id=rejected_review_row.id,
        moderator_user_id=moderator.id,
        as_of=MOD_AS_OF,
    )
    assert rejected.status == "rejected"

    published = svc.publish_review(
        salon_id=salon.id,
        review_id=review.id,
        moderator_user_id=moderator.id,
        as_of=MOD_AS_OF,
    )
    assert published.status == "published"
    assert published.published_at == MOD_AS_OF
    assert published.moderated_by_user_id == moderator.id

    salon_b, _, _ = _seed_bookable_salon(db_session)
    with pytest.raises(Exception) as exc_info:
        svc.publish_review(
            salon_id=salon_b.id,
            review_id=review.id,
            moderator_user_id=moderator.id,
            as_of=MOD_AS_OF,
        )
    from app.services.review.errors import ReviewNotFoundError

    assert isinstance(exc_info.value, ReviewNotFoundError)

    hidden = svc.hide_review(
        salon_id=salon.id,
        review_id=review.id,
        moderator_user_id=moderator.id,
        as_of=MOD_AS_OF,
    )
    assert hidden.status == "hidden"


def test_moderation_invalid_transition(
    db_session: Session,
    public_client: TestClient,
    bookable_context: tuple,
) -> None:
    base, salon, _staff, _service, booking_id, token, _booking = bookable_context
    public_client.post(
        f"{base}/bookings/{booking_id}/review",
        json={"token": token, "rating": 3},
    )
    review = db_session.scalar(
        select(Review).where(Review.salon_id == salon.id, Review.booking_id == booking_id)
    )
    assert review is not None
    moderator = _seed_moderator(db_session)
    svc = ReviewService(db_session)
    svc.reject_review(
        salon_id=salon.id,
        review_id=review.id,
        moderator_user_id=moderator.id,
        as_of=MOD_AS_OF,
    )
    from app.services.review.errors import ReviewValidationError

    with pytest.raises(ReviewValidationError):
        svc.publish_review(
            salon_id=salon.id,
            review_id=review.id,
            moderator_user_id=moderator.id,
            as_of=MOD_AS_OF,
        )


def test_public_read_only_published_and_tenant_scoped(
    db_session: Session,
    public_client: TestClient,
) -> None:
    salon_a, staff_a, _service_a = _seed_bookable_salon(db_session)
    salon_b, staff_b, _service_b = _seed_bookable_salon(db_session)
    moderator = _seed_moderator(db_session)
    svc = ReviewService(db_session)

    def _insert_review(
        *,
        salon: Salon,
        staff: Staff,
        status: str,
        published_at: datetime | None,
    ) -> Review:
        customer = Customer(salon_id=salon.id, full_name="C")
        db_session.add(customer)
        db_session.flush()
        review = Review(
            salon_id=salon.id,
            booking_id=None,
            customer_id=customer.id,
            staff_id=staff.id,
            rating=5,
            title="t",
            body="b",
            status=status,
            published_at=published_at,
        )
        db_session.add(review)
        db_session.flush()
        return review

    pub_a = _insert_review(
        salon=salon_a,
        staff=staff_a,
        status="published",
        published_at=MOD_AS_OF,
    )
    _insert_review(salon=salon_a, staff=staff_a, status="pending", published_at=None)
    _insert_review(salon=salon_a, staff=staff_a, status="rejected", published_at=None)
    _insert_review(salon=salon_a, staff=staff_a, status="hidden", published_at=MOD_AS_OF)
    pub_b = _insert_review(
        salon=salon_b,
        staff=staff_b,
        status="published",
        published_at=MOD_AS_OF,
    )
    del pub_b

    list_a = public_client.get(f"/api/v1/public/salons/{salon_a.slug}/reviews")
    assert list_a.status_code == 200
    ids_a = {row["id"] for row in list_a.json()["reviews"]}
    assert str(pub_a.id) in ids_a
    assert len(ids_a) == 1

    list_b = public_client.get(f"/api/v1/public/salons/{salon_b.slug}/reviews")
    assert list_b.status_code == 200
    assert len(list_b.json()["reviews"]) == 1
    assert list_b.json()["reviews"][0]["id"] != str(pub_a.id)

    del moderator, svc
