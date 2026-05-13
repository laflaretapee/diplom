# Japonica CRM — Agent Handoff Log

> Файл для передачи контекста между сессиями. Обновляй при каждой значимой работе.

---

## Проект

**Japonica CRM** — дипломная работа. Система управления сетью суши-ресторанов (франчайзинг).

- Backend: FastAPI + SQLAlchemy 2.0 async + Alembic + Celery + Redis
- Frontend: React 18 + TypeScript + Vite + Ant Design 5 + TanStack Query + Zustand
- DB: PostgreSQL
- Инфраструктура: Docker Compose + Nginx

Локальные порты: `18000` (API), `18080` (Nginx), `15173` (Frontend), `5433` (Postgres), `6380` (Redis)

---

## Состояние на 2026-05-13

### Задачи
- **Всего задач в tasks.json**: 82
- **Выполнено**: 82 / 82 — все задачи закрыты
- **Pending**: 0

### Backend модули
| Модуль | Описание |
|--------|----------|
| `auth` | JWT login, refresh cookie, logout, /me |
| `users` | User CRUD, назначение точек (super_admin) |
| `orders` | Заказы, статусные переходы |
| `inbound` | Внешний API-Key intake (сайт, агрегаторы) |
| `realtime` | WebSocket очередь заказов per-point |
| `warehouse` | Ингредиенты, остатки, тех.карты, движения, аудит |
| `franchisee` | CRM-воронка, 8 стадий, чеклисты, заметки, точки |
| `notifications` | Telegram-linking, preferences |
| `analytics` | Revenue, dishes, channels, summary, forecast, anomalies |
| `documents` | Приватное хранилище файлов, RBAC, audit log |
| `kanban` | Доски, колонки, карточки, комментарии, custom fields, вложения |
| `points` | Список точек |

### Frontend страницы
- `LoginPage` — реальный auth, role-aware redirect
- `DashboardPage` — role-aware, live WS refetch
- `OrderQueuePage` — kanban 4 колонки + drag-and-drop + WS
- `OrderHistoryPage` — история + фильтры
- `WarehousePage` — ингредиенты, остатки, приход, история
- `FranchiseeKanbanPage` — CRM-воронка (super_admin)
- `DishesPage` — управление блюдами и каналами продаж
- `DocumentsPage` — загрузка, аудит, скачивание
- `KanbanBoardsPage` + `KanbanBoardPage` — канбан-доски с drag-and-drop
- `AIAssistantPage` — ИИ-ассистент (super_admin, franchisee)

### Alembic миграции (применены)
```
0001 → 0002 (orders) → 0003 (warehouse) → 0004 (dishes) →
0005 (franchisees) → 0006 (user_notification_settings) →
0007 (dish_sales_channels) → 0008 (documents) →
0009 (kanban) → 0010 (domain_events) →
0011 (kanban_tasks_full)
```

### Незакоммиченные изменения (на 2026-05-13)
1. `backend/alembic/versions/20260417_0011_kanban_tasks_full.py`
   - Исправлен `down_revision`: `20260331_0010` → `20260331_0011`
   - Это фикс цепочки миграций

2. `frontend/vite.config.ts`
   - Добавлена функция `collectAllowedHosts()` для парсинга `VITE_ALLOWED_HOSTS`, `FRONTEND_ORIGIN`, `NGINX_SERVER_NAME`
   - Добавлен `allowedHosts` в `server` и `preview`
   - Вероятно сделано для production-деплоя (VPS)

### Demo аккаунты (seed)
| Email | Password | Роль |
|-------|----------|------|
| `admin@japonica.example.com` | `Admin1234!` | super_admin |
| `franchisee-ufa1@japonica.example.com` | `Demo1234!` | franchisee |
| `manager-ufa1@japonica.example.com` | `Demo1234!` | point_manager |
| `staff-ufa1@japonica.example.com` | `Demo1234!` | staff |

Seed-скрипт: `backend/scripts/seed_demo.py`

---

## Ключевые команды

```bash
# Запустить стек
docker compose up -d

# Применить миграции
docker compose exec api alembic upgrade head

# Запустить seed
docker compose exec api python backend/scripts/seed_demo.py

# Frontend typecheck + build
cd frontend && npm run typecheck && npm run build

# Backend lint
uv run ruff check backend

# Экспорт OpenAPI
uv run python backend/scripts/export_openapi.py --output docs/openapi.json
```

---

## Что может потребоваться дальше

- Закоммитить незакоммиченные изменения (migration fix + vite config)
- Деплой на VPS (конфиг есть в `deploy/`)
- Дополнительные фичи по запросу (если диплом расширяется)
- Подготовка к защите (demo package готов в `docs/demo/`)

---

## История сессий (кратко)

| Сессия | Что сделано |
|--------|-------------|
| 1-5 | Скелет, auth/RBAC, orders, warehouse, WebSocket, franchisee, Celery |
| 6-9 | Analytics, Telegram, AI provider, security (CSRF, rate limit), CI/CD |
| 10-15 | Demo contour: реальный auth, drag-and-drop, русификация, demo seed |
| 16-17 | Sprint 1: Documents + Kanban модули, Telegram mock commands, тесты |
| — | Последний коммит: "Kanban task management: state machine, Telegram notifications, deadline scheduler" |
