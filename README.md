# NIV Reservation System

Phase 1: project skeleton, configuration, database base, first migration, health endpoint.

## Local run (Docker)

    cp .env.example .env
    docker compose up --build

Backend: http://localhost:8000/healthz

## Local run (without Docker)

    python -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev]"
    cp .env.example .env          # adjust DATABASE_URL to a running PostgreSQL
    alembic upgrade head
    uvicorn app.main:app --reload

## Tests

    pytest -q

## Migrations

    alembic revision -m "describe change" --autogenerate
    alembic upgrade head
    alembic downgrade -1

## Phase 2: backend core

- Domain rules (pure, testable): `app/domain/` (pricing, time rules, payment rules, statuses, errors).
- Services (use cases): `app/services/`. Services flush; the API layer commits.
- Internal API (service token required): `/internal/quote`, `/internal/reservations`, receipt, payment verify/reject, confirm (assigns tables), reject, cancel.
- Overlap protection: `FOR UPDATE` row locks plus a PostgreSQL EXCLUDE constraint on `table_bookings` (migration 0002, needs `btree_gist`).

Run tests:

    pytest -q                                           # unit tests
    TEST_DATABASE_URL=postgresql+asyncpg://niv:niv_password@localhost:5432/niv_test pytest -q   # + integration


## Phase 6: reports and worker

- Worker process: `python -m app.worker.main`. Runs reminders, unpaid expiry, the nightly report (22:00 Tehran) and the monthly Excel (last day of month, 23:00). Each job runs once per key (`job_runs`).
- Reports are sent to active managers through the management bot token (`MANAGEMENT_BOT_TOKEN`).
- Manual: `GET /admin/reports/daily`, `GET /admin/reports/monthly.xlsx?ym=YYYY-MM`.
- Financials use verified payments only.
