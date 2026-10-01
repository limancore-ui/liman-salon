#!/usr/bin/env bash
# Manual smoke: run both one-shot workers once (requires DATABASE_URL).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m app.jobs.expire_pending_holds
python -m app.jobs.process_pending_notifications
