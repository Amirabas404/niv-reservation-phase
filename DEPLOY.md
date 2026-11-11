# Deploying NIV on Railway

## Services (one Railway project)

| Service | Start command | Public | Notes |
|---|---|---|---|
| postgres | Railway PostgreSQL plugin | no | Enable Railway backups too (see below) |
| redis | Railway Redis plugin | no | Used by both bots for FSM state |
| backend | `sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT"` | yes (internal API) | Healthcheck path: `/healthz` |
| customer-bot | `python -m bots.customer.main` | yes (webhook) | Set `WEBHOOK_BASE_URL` to its public domain |
| management-bot | `python -m bots.management.main` | yes (webhook) | Set `WEBHOOK_BASE_URL` to its public domain |
| worker | `python -m app.worker.main` | no | Exactly one replica is recommended |

All services use the same Dockerfile. Set the start command per service.

Run database migrations once per release. The backend start command already runs `alembic upgrade head`. Do not scale the backend to zero during a release.

## Required variables (set per service, or shared through Railway variable references)

- `DATABASE_URL` (`postgresql+asyncpg://...`), `REDIS_URL`
- `INTERNAL_SERVICE_TOKEN` (customer bot to backend), `ADMIN_SERVICE_TOKEN` (management bot to backend). Use two different random values.
- `CUSTOMER_BOT_TOKEN`, `MANAGEMENT_BOT_TOKEN`
- `BACKEND_URL` (customer bot, private network URL of backend), `MANAGEMENT_BOT_BACKEND_URL` (management bot)
- `WEBHOOK_BASE_URL` and `WEBHOOK_SECRET` for each bot (the secret must be different for each bot)
- `NOTIFIER_ACTOR_TELEGRAM_ID` (a manager's Telegram ID)
- `STORAGE_PROVIDER=r2` and the four `STORAGE_*` variables for the private R2 bucket
- `TIMEZONE=Asia/Tehran`

Never commit `.env`. Never put the card number in code: it is stored in the database through the management bot.

## First-time setup

1. Deploy backend. Confirm `GET /healthz` returns `{"status":"ok"}`.
2. Create the first manager from a Railway shell on the backend service:
   `python -m app.cli add-admin --telegram-id <ID> --role manager --name "<name>"`
3. Insert the bank card once (the card is never stored in code). Run it in a Railway PostgreSQL shell:
   `INSERT INTO system_settings (key, value, version) VALUES ('bank_card', '{"card_number":"<16 digits>","owner_name":"<name>"}', 1);`
   Later changes can be made from the management bot's settings, which validate the card number.
4. Deploy customer-bot and management-bot with their webhook settings.
5. Deploy worker last.

## Backups

- The worker writes a daily `pg_dump` (gzipped) to the private R2 bucket under `backups/` at `BACKUP_TIME` and keeps `BACKUP_RETENTION_DAYS` days.
- Also enable Railway's managed backups on the PostgreSQL plugin.
- Test a restore at least once before going live: download a backup, `gunzip`, and load it into a scratch database.

## Monitoring

- Railway healthchecks: backend `/healthz`.
- Logs: each service logs to Railway. Watch for `worker tick failed`, `outbox loop error`, and `notifier loop error`.
- Failed Telegram deliveries are logged and retried automatically (notifications, outbox).

## Security checklist before going live

- R2 bucket is private (no public access, no custom domain). Receipts are served only through the backend with the Audit Log.
- Bot tokens and service tokens are only in Railway variables.
- The backend port is not exposed publicly unless needed. Bots reach it on Railway's private network.
- Rotate tokens if a log or screenshot ever shows one.
