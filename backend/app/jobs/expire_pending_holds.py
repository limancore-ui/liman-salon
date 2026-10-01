"""One-shot job: expire all stale pending booking holds (global sweeper)."""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.services.booking.service import BookingService


def run() -> int:
    as_of = datetime.now(timezone.utc)
    session = SessionLocal()
    try:
        count = BookingService(session).expire_all_stale_pending_holds(as_of=as_of)
        session.commit()
        print(f"expired_pending_holds={count}")
        return 0
    except Exception:
        session.rollback()
        return 1
    finally:
        session.close()


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
