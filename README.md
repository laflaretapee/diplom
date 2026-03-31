# Japonica CRM

Japonica CRM is a modular monolith for franchise restaurant operations. It combines order management, warehouse control, franchisee onboarding, notifications, analytics, and an AI analyst interface in one stack.

## Stack

- Backend: FastAPI, SQLAlchemy 2.0 async, Alembic
- Frontend: React, TypeScript, Vite, Ant Design
- Database: PostgreSQL
- Broker / cache: Redis
- Background jobs: Celery + beat
- Reverse proxy: Nginx

## Quick Start

1. Copy env file:

```bash
cp .env.example .env
```

2. Start the stack:

```bash
docker compose up -d
```

3. Check health:

```bash
curl -sS http://127.0.0.1:18000/health
curl -sS http://127.0.0.1:18080/health
```

4. Open services:

- Frontend dev UI: `http://127.0.0.1:15173`
- API through Nginx: `http://127.0.0.1:18080/api/v1`
- Swagger UI: `http://127.0.0.1:18000/docs`
- OpenAPI schema: `http://127.0.0.1:18000/openapi.json`

Frontend now uses real auth endpoints with access token in store, refresh through cookie + CSRF, role-based redirects, and session restore after reload.

## Demo Package

Demo-ready materials live in `docs/demo/`:

- `docs/demo/use-cases.md` — working use cases and demo accounts
- `docs/demo/presentation-script.md` — 7–10 minute script
- `docs/demo/fallback-script.md` — backup route if WS or AI misbehave
- `docs/demo/checklist.md` — pre-demo checklist

## Core Commands

### Frontend

```bash
cd frontend
npm ci
npm run typecheck
npm run build
```

### Backend

```bash
uv sync --group dev
uv run ruff check backend
uv run python backend/scripts/export_openapi.py --output docs/openapi.json
```

### Compose

```bash
docker compose config
docker compose -f docker-compose.yml -f deploy/docker-compose.vps.yml config
```

## Environment

Key variables are documented in `.env.example`.

Important groups:

- app/runtime: `APP_ENV`, `API_PREFIX`, `VITE_API_BASE_URL`
- database/redis: `DATABASE_URL`, `REDIS_URL`
- auth: `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET_KEY`
- notifications: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`
- AI: `AI_BACKEND`, `QWEN_*`, `OLLAMA_*`
- security: `COOKIE_SECURE`, `COOKIE_SAMESITE`, rate-limit settings
- production TLS: `NGINX_SERVER_NAME`, `LETSENCRYPT_EMAIL`

## Module Map

- `backend/app/modules/auth` — JWT auth, refresh cookie, current user
- `backend/app/modules/users` — user CRUD and point assignments
- `backend/app/modules/orders` — orders and status flow
- `backend/app/modules/realtime` — WebSocket order updates
- `backend/app/modules/warehouse` — ingredients, stock, supply, movements, dishes
- `backend/app/modules/franchisee` — franchisee pipeline, tasks, notes, points
- `backend/app/modules/notifications` — Telegram linking and preferences
- `backend/app/modules/analytics` — dashboards, anomalies, forecast, AI assistant

Detailed architecture notes live in `docs/architecture.md`.

## Security Notes

- Refresh token uses an HTTP-only cookie.
- `csrf_token` cookie + `X-CSRF-Token` header protect refresh/logout.
- Sensitive endpoints use Redis-backed rate limiting.
- CORS is limited to configured origins.
- Nginx adds baseline hardening headers in both local and production-facing configs.

## Production / VPS

Base local compose remains in `docker-compose.yml`.

Production-facing HTTPS overlay lives in `deploy/docker-compose.vps.yml` and uses:

- Nginx TLS config from `nginx/production.conf.template`
- Certbot renewal service
- deploy entrypoint `deploy/deploy_vps.sh`

GitHub Actions deployment expects these repository secrets:

- `VPS_HOST`
- `VPS_USER`
- `VPS_SSH_KEY`
- `VPS_APP_DIR`

## Verification Scripts

- Security: `backend/scripts/verify_security.py`
- Analytics + AI: `backend/scripts/verify_ai_analytics_block.py`
- Weekly report: `backend/scripts/verify_weekly_revenue_report.py`
- Notifications preferences: `backend/scripts/verify_notification_preferences.py`
- Franchisee notifications: `backend/scripts/verify_franchisee_notifications.py`
- Load testing: `backend/scripts/loadtest_orders_ws.py`

Load-testing notes and baseline metrics are in `docs/load-testing.md`.
