"""One-shot job: deliver due pending notification outbox rows (stub provider)."""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.services.notifications.service import NotificationService


def run() -> int:
    as_of = datetime.now(timezone.utc)
    session = SessionLocal()
    try:
        count = NotificationService(session).process_due_pending(as_of=as_of)
        session.commit()
        print(f"processed_pending_notifications={count}")
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
