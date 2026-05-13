# Architecture

## Overview

Джейсан is a modular FastAPI monolith with a React/Vite frontend, PostgreSQL as the primary database, Redis for ephemeral state and queue transport, and Celery for background jobs.

## Runtime Pieces

- `backend/app/main.py`
  Starts the FastAPI app, healthcheck, middleware, and module routers.
- `frontend/`
  React + TypeScript admin UI with role-aware routing.
- `postgres`
  Primary relational store for users, points, orders, warehouse, franchisee pipeline, and analytics source data.
- `redis`
  Used for Celery broker/result backend, Telegram linking codes, and rate limiting buckets.
- `worker`
  Celery worker + beat for notifications, overdue scans, and weekly revenue reports.
- `nginx`
  Reverse proxy for frontend and backend; production overlay adds HTTPS and Certbot integration.

## Module Boundaries

### Auth and Access

- `backend/app/modules/auth`
  JWT login, refresh cookie rotation, logout, current user info.
- `backend/app/modules/users`
  Super-admin user CRUD and point assignments.
- `backend/app/core/deps.py`
  RBAC and tenant-scoping dependencies.

### Orders and Realtime

- `backend/app/modules/orders`
  Order creation, listing, fetch by id, status transitions.
- `backend/app/modules/inbound`
  Public API-key based order intake from website, mobile app, Telegram, VK.
- `backend/app/modules/realtime`
  WebSocket stream per point for order queue updates.

### Warehouse

- `backend/app/modules/warehouse`
  Ingredient catalog, stock movements, supply endpoint, audit log, low-stock checks, dishes and recipe cards.

### Franchisee Pipeline

- `backend/app/modules/franchisee`
  Franchisee CRUD, stage pipeline, checklist tasks, notes/history, and point binding.

### Notifications

- `backend/app/modules/notifications`
  Telegram account linking and notification preferences.
- `backend/app/tasks/notifications.py`
  Async delivery tasks for orders, low stock, franchisee events, overdue tasks, weekly revenue reports.

### Analytics and AI

- `backend/app/modules/analytics`
  Revenue, channels, dish analytics, summary, anomalies, procurement forecast, and AI analyst chat.
- `backend/app/core/ai.py`
  Pluggable AI provider abstraction for disabled mode, Qwen API, or Ollama.

## Security

- Refresh token is stored in an HTTP-only cookie.
- CSRF protection is applied to refresh/logout via a double-submit `csrf_token` cookie and `X-CSRF-Token` header.
- Sensitive endpoints use Redis-backed rate limiting.
- CORS is restricted to configured origins and credentials are allowed only for those origins.

## Production Deployment

- Base local stack: `docker-compose.yml`
- VPS overlay with HTTPS/Certbot: `deploy/docker-compose.vps.yml`
- Deploy entrypoint for CI/CD: `deploy/deploy_vps.sh`

## API Documentation

- Interactive Swagger UI: `/docs`
- ReDoc: `/redoc`
- Raw schema: `/openapi.json`
- Offline export: `python backend/scripts/export_openapi.py --output docs/openapi.json`
