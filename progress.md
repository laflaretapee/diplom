# 2026-03-30

- Инициализирован репозиторий и создан служебный лог выполнения в `logs/execution-2026-03-30.md`.
- Запущены параллельные субагенты: один на `frontend/**`, второй на ops-скелет (`docker-compose.yml`, `.env.example`, `nginx/**`).
- Локально создан backend-скелет под FastAPI, модульный монолит, SQLAlchemy/Alembic и базовые модели доступа.
- Установлены backend и frontend зависимости, frontend прошёл `npm run typecheck` и `npm run build`.
- Поднят Docker Compose стек на локальных host-портах `18080` (nginx), `18000` (api), `15173` (frontend), `5433` (postgres), `6380` (redis).
- Живая верификация пройдена: `api`, `frontend`, `nginx`, `postgres`, `redis`, `worker` в статусе healthy или running, `curl http://127.0.0.1:18000/health` вернул `{\"status\":\"ok\"}`, а `curl http://127.0.0.1:18080/api/v1/orders/status` вернул `{\"module\":\"orders\",\"status\":\"scaffolded\"}`.
- Alembic проверен на реальной БД: выполнены `upgrade head`, `downgrade base`, повторный `upgrade head`.
- Скрипт `backend/scripts/verify_access_models.py` подтвердил, что модели `User`, `Point`, `UserPoint` работают на живой БД и дубликат связи пользователь-точка отклоняется ограничением.
- Закрыты задачи: `TASK-001`, `TASK-002`, `TASK-003`, `TASK-004`, `TASK-005`, `TASK-008`.
- Следующий шаг: переход к `TASK-006` и `TASK-007` — JWT auth, refresh-cookie и RBAC/tenant scoping.

## 2026-03-30 (сессия 2)

- Реализован `backend/app/core/security.py`: `hash_password`, `verify_password` (через `bcrypt` напрямую, без passlib из-за несовместимости passlib 1.7.4 + bcrypt 5.x), `create_access_token`, `create_refresh_token`, `decode_access_token`, `decode_refresh_token`.
- Реализованы `auth/schemas.py` (LoginRequest, TokenResponse, UserInfo, LoginResponse), `auth/service.py` (authenticate_user, build_login_response), `auth/router.py` (/login, /refresh, /logout, /me).
- Реализован `backend/app/core/deps.py`: `get_current_user` (Bearer JWT), `require_roles(*roles)` factory, шорткаты `require_super_admin`/`require_franchisee_or_above`/`require_manager_or_above`/`require_any_role`, `verify_point_access` (tenant scoping), `require_point_access(param)` factory.
- Добавлен скрипт `backend/scripts/seed_admin.py` и `backend/scripts/verify_rbac.py`.
- E2E верификация пройдена:
  - `POST /api/v1/auth/login` → access token + httpOnly refresh cookie ✓
  - `POST /api/v1/auth/refresh` → новый access token + ротация refresh cookie ✓
  - `POST /api/v1/auth/logout` → HTTP 204 ✓
  - `GET /api/v1/auth/me` с токеном → 200, без токена → 401, с невалидным → 401 ✓
  - Tenant scoping: staff→своя точка PASS, staff→чужая точка 403, super_admin→любая точка PASS ✓
- Закрыты задачи: `TASK-006`, `TASK-007`.
- Следующий шаг: `TASK-009` (управление пользователями для super_admin) и `TASK-010` (модель Order + базовый API заказов).

## 2026-03-30 (сессия 3)

- Реализован модуль `backend/app/modules/users/` (TASK-009): 6 эндпоинтов (POST/GET/PATCH users, assign/unassign points), все защищены `require_super_admin`.
- Все тесты TASK-009 прошли: 201 создание, 401 без токена, 403 под staff.
- Закрыта задача: `TASK-009`.
- Субагент 2 завершил: TASK-010 (Order model + API с валидацией статус-переходов), TASK-011 (payment_types per point + валидация при создании заказа), TASK-016 (Ingredient, StockItem, StockMovement + миграция 0003).
- Применены миграции 0002 (orders) и 0003 (warehouse). Все тесты прошли.
- Закрыты задачи: `TASK-009`, `TASK-010`, `TASK-011`, `TASK-016`.
- Следующий шаг (параллельно): TASK-012 (inbound API), TASK-015 (frontend history), TASK-017+018 (ingredient catalog + dishes).

## 2026-03-30 (сессия 4)

- **TASK-012**: публичный `POST /api/v1/inbound/orders` с X-API-Key аутентификацией, source_channel сохраняется корректно, reuse логики orders.service.
- **TASK-015**: `OrderHistoryPage` (Ant Design, React Query, zustand), маршрут `/orders/history`, фильтры по точке/статусу/датам, цветовые бейджи статусов. Typecheck: 0 ошибок.
- **TASK-017**: warehouse API — ингредиенты (CRUD), stock по точке с `is_below_minimum`, движения (in/out/adjustment с валидацией остатка).
- **TASK-018**: модели Dish + DishIngredient, миграция 0004, эндпоинты управления блюдами и тех.картами. Деактивация + фильтрация работают.
- Миграция 0004 применена успешно.
- Закрыты задачи: `TASK-012`, `TASK-015`, `TASK-017`, `TASK-018`.
- Следующий шаг: `TASK-013` (WebSocket real-time заказы), `TASK-014` (kanban UI), `TASK-019`+.

## 2026-03-30 (сессия 5)

- **TASK-013**: WebSocket эндпоинт `GET /api/v1/ws/orders/{point_id}?token=<jwt>` — ConnectionManager, broadcast при create/status change, keep-alive ping.
- **TASK-014**: `OrderQueuePage` — kanban 4 колонки (Новый/В работе/Готов/Выдан), WS + fallback polling, смена статусов одним кликом. TypeScript: 0 ошибок.
- **TASK-019**: `write_off_for_order` — автосписание ингредиентов по тех.картам при создании заказа (fire-and-forget). Тест: qty 10→6 после 2 порций.
- **TASK-020**: `POST /warehouse/stock/supply` + `GET /warehouse/stock/movements` — приход с поставщиком, история движений с ingredient_name.
- **TASK-024**: модели Franchisee + FranchiseeTask, миграция 0005 применена.
- **TASK-025**: CRUD карточки франчайзи, tenant scoping для роли franchisee.
- **TASK-026**: pipeline стадий (8 статусов), чеклисты задач с `stage_progress`.
- **TASK-032**: Celery app + очередь уведомлений (send_order_notification, send_low_stock_notification) + beat schedule. Worker перезапущен, 4 задачи зарегистрированы.
- Закрыты: `TASK-013`, `TASK-014`, `TASK-019`, `TASK-020`, `TASK-024`, `TASK-025`, `TASK-026`, `TASK-032`.
- Следующий шаг (параллельно): TASK-021+022 (audit+low_stock), TASK-027+028+029 (franchisee UI+history), TASK-030+035 (Telegram+analytics).

## 2026-03-31 (сессия 6)

- **TASK-021**: подтверждён и доведён аудит склада. Добавлен `backend/scripts/verify_audit.py`; audit endpoint теперь свежо проверен на author/system rows и tenant-scope (`403` на чужую точку для point_manager).
- **TASK-022**: исправлен low_stock-trigger на semantics “только при crossing above->below”, без дублей при последующих списаниях ниже порога; хук добавлен и в `write_off_for_order`. Добавлены `backend/scripts/verify_low_stock.py` и `backend/scripts/trigger_live_low_stock.py`.
- **TASK-030**: реализован Telegram-linking flow через Redis (`/notifications/telegram/link`, `/telegram/status`, `/telegram/webhook`, `/telegram/unlink`), добавлен `backend/app/core/telegram.py`, а `send_order_notification` теперь резолвит `telegram_chat_id` point_manager-ов. Добавлены `backend/scripts/verify_telegram_link.py` и `backend/scripts/prepare_notification_recipient.py`.
- **TASK-035**: заменён analytics scaffold на реальные агрегирующие endpoint’ы `/analytics/revenue`, `/analytics/dishes`, `/analytics/channels`, `/analytics/summary` с period filtering и tenant-scoping. Добавлен `backend/scripts/verify_analytics.py`.
- **TASK-027**: добавлена `frontend/src/pages/FranchiseeKanbanPage.tsx`, маршрут `/franchisee` и пункт меню для `super_admin`; карточки показывают стадии и процент чеклиста.
- **TASK-028**: backend и UI для franchisee notes/history реализованы через JSON в `franchisees.notes`.
- **TASK-029**: backend attach/detach/list franchisee points + реальный `GET /api/v1/points`; UI вкладка точек в franchisee modal подключена.
- Живая верификация пройдена:
  - `docker exec diplom-api-1 /workspace/.venv/bin/python /workspace/backend/scripts/verify_audit.py`
  - `docker exec diplom-api-1 /workspace/.venv/bin/python /workspace/backend/scripts/verify_low_stock.py`
  - live API path `warehouse/ingredients -> stock/supply -> stock/movements` дал `notifications.send_low_stock_notification` в `worker`-логе
  - `docker exec diplom-api-1 /workspace/.venv/bin/python /workspace/backend/scripts/verify_telegram_link.py`
  - live order creation после подготовки `notify-manager@japonica.example.com` дал `send_order_notification ... to ['777888999']` в `worker`-логе
  - `docker exec diplom-api-1 /workspace/.venv/bin/python /workspace/backend/scripts/verify_analytics.py`
  - `cd /home/dinar/diplom/frontend && npm run typecheck`
- Закрыты задачи: `TASK-021`, `TASK-022`, `TASK-027`, `TASK-028`, `TASK-029`, `TASK-030`, `TASK-035`.
- Следующий логический блок: `TASK-023` (UI склада), `TASK-031` (user notification settings), `TASK-033` и `TASK-034` (domain notifications), `TASK-036` (dashboards).

## 2026-03-31 (сессия 7)

- **TASK-023**: добавлена `frontend/src/pages/WarehousePage.tsx` и интегрирован маршрут `/warehouse`; экран склада переведён в noir-стиль по референсу из `stitch (5)/stitch/warehouse_management`, поддерживает список ингредиентов, остатки, историю движений, формы прихода и корректировки.
- **TASK-036**: `frontend/src/pages/DashboardPage.tsx` заменён на role-aware dashboard по референсу `stitch (5)/stitch/dashboard_admin`; для `point_manager/staff` включён live-refetch через WebSocket, для сетевых ролей — analytics widgets с фильтрами.
- Приложение визуально приведено к `Japonica noir`: обновлены `frontend/src/app/theme.ts`, `frontend/src/styles/global.css`, `frontend/src/components/AppShell.tsx`, добавлен пункт меню склада для ролей `super_admin`, `franchisee`, `point_manager`.
- **TASK-031**: в `users` добавлено поле `notification_settings` (миграция `20260331_0006_add_user_notification_settings.py`), реализованы `GET/PATCH /api/v1/notifications/preferences` и единый merge default preferences.
- **TASK-033**: `send_order_notification` теперь реально отправляет `order_created` и `order_cancelled` только разрешённым point_manager-ам точки, `send_low_stock_notification` теперь резолвит получателей по точке и уважает пользовательские preferences.
- **TASK-034**: добавлены `send_franchisee_stage_notification`, `send_franchisee_task_status_notification`, `send_overdue_franchisee_task_notifications`; router франчайзи теперь публикует stage/task events, а worker запущен с `--beat`, поэтому overdue scan реально активен в compose-стеке.
- Живая верификация пройдена:
  - `cd /home/dinar/diplom/frontend && npm run typecheck`
  - `cd /home/dinar/diplom/frontend && npm run build`
  - `docker compose config`
  - `docker exec diplom-api-1 /workspace/.venv/bin/alembic -c /workspace/alembic.ini upgrade head`
  - `docker exec diplom-api-1 /workspace/.venv/bin/python /workspace/backend/scripts/verify_notification_preferences.py`
  - `docker exec diplom-api-1 /workspace/.venv/bin/python /workspace/backend/scripts/verify_franchisee_notifications.py`
  - live HTTP: `GET/PATCH /api/v1/notifications/preferences`
  - live HTTP: `POST /api/v1/orders` + `PATCH /api/v1/orders/{id}/status` дал `order_created` и `order_cancelled` на `['777888999']` в `worker`-логе
  - live low_stock e2e: threshold crossing дал `Low stock alert delivered ... recipients=['777888999']` в `worker`-логе
- Закрыты задачи: `TASK-023`, `TASK-031`, `TASK-033`, `TASK-034`, `TASK-036`.
- Следующий логический блок: `TASK-037`, `TASK-038`, `TASK-039`, `TASK-040`, `TASK-041`.

## 2026-03-31 (сессия 8)

- **TASK-037**: добавлен конфигурируемый AI provider layer в `backend/app/core/ai.py` и расширен `backend/app/core/config.py`/`.env.example` для `AI_BACKEND`, `QWEN_*`, `OLLAMA_*`, timeout-настроек. Переключение backend теперь не требует менять бизнес-код.
- **TASK-038**: реализован `POST /api/v1/analytics/assistant/chat` с evidence-backed контекстом из CRM-данных; ответ возвращает `provider`, `used_fallback`, `evidence`, `suggestions`, `context_scope`. На frontend подключена `AIAssistantPage` в стиле `stitch (5)`, маршрут `/assistant` и меню для `super_admin`/`franchisee`.
- **TASK-039**: реализован `GET /api/v1/analytics/forecast` — прогноз закупки по точке на основе истории заказов, тех.карт и текущих остатков.
- **TASK-040**: реализован `GET /api/v1/analytics/anomalies` — сигналы по падению выручки и подозрительным списаниям со сравнением текущего и базового окна.
- **TASK-041**: реализован `notifications.send_weekly_revenue_report`, beat-планировщик переведён на реальную weekly-report задачу, а отчёт формируется по scope пользователя и уважает `weekly_revenue_report` preference.
- Добавлены verify-скрипты:
  - `backend/scripts/verify_ai_provider.py`
  - `backend/scripts/verify_ai_analytics_block.py`
  - `backend/scripts/verify_weekly_revenue_report.py`
- Живая верификация пройдена:
  - `docker compose -f /home/dinar/diplom/docker-compose.yml restart api worker`
  - `curl -sS http://127.0.0.1:18000/health`
  - `docker exec diplom-api-1 /workspace/.venv/bin/python /workspace/backend/scripts/verify_ai_provider.py`
  - `docker exec diplom-api-1 /workspace/.venv/bin/python /workspace/backend/scripts/verify_ai_analytics_block.py`
  - `docker exec diplom-api-1 /workspace/.venv/bin/python /workspace/backend/scripts/verify_weekly_revenue_report.py`
  - `docker logs diplom-worker-1 --tail=40` показал `notifications.send_weekly_revenue_report ... succeeded`
  - `cd /home/dinar/diplom/frontend && npm run typecheck`
  - `cd /home/dinar/diplom/frontend && npm run build`
  - `docker compose config`
- Закрыты задачи: `TASK-037`, `TASK-038`, `TASK-039`, `TASK-040`, `TASK-041`.
- Следующий логический блок: `TASK-042`, `TASK-043`, `TASK-044`, `TASK-045`, `TASK-046`.

## 2026-03-31 (сессия 9)

- **TASK-042**: добавлены Redis-backed rate limits для чувствительных endpoint-ов (`auth/login`, `auth/refresh`, inbound orders, Telegram link/webhook) через `backend/app/core/rate_limit.py`; в `auth/router.py` добавлены secure cookie settings, `csrf_token` double-submit cookie и обязательный `X-CSRF-Token` для refresh/logout; в `main.py` включены CORS middleware и базовые security headers; frontend `apiClient` теперь автоматически прокидывает CSRF header для mutating requests.
- **TASK-043**: dev nginx hardening усилен в `nginx/default.conf`; добавлены production TLS template `nginx/production.conf.template` и VPS overlay `deploy/docker-compose.vps.yml` с Certbot renewal loop. Это production-ready scaffold для домена и Let's Encrypt.
- **TASK-044**: добавлены GitHub Actions workflows `.github/workflows/ci.yml` и `.github/workflows/deploy.yml`, а также remote deploy script `deploy/deploy_vps.sh`.
- **TASK-045**: полностью переписан `README.md`, добавлены `docs/architecture.md`, offline-export utility `backend/scripts/export_openapi.py`, зафиксированы `/docs`, `/redoc`, `/openapi.json`, локальный запуск, env и архитектурные границы.
- **TASK-046**: добавлен `backend/scripts/loadtest_orders_ws.py` и baseline отчёт `docs/load-testing.md`; live-прогон выполнен с фактическими метриками latency и WS delivery.
- Живая/структурная верификация пройдена:
  - `docker compose -f /home/dinar/diplom/docker-compose.yml restart api nginx`
  - `docker exec diplom-api-1 /workspace/.venv/bin/python /workspace/backend/scripts/verify_security.py`
  - `curl -I http://127.0.0.1:18080/`
  - `docker compose -f docker-compose.yml -f deploy/docker-compose.vps.yml config`
  - `docker exec diplom-api-1 /workspace/.venv/bin/python /workspace/backend/scripts/export_openapi.py --output /tmp/openapi.json`
  - `docker exec diplom-api-1 /workspace/.venv/bin/python /workspace/backend/scripts/loadtest_orders_ws.py --api-base-url http://nginx/api/v1 --ws-clients 2 --orders 3 --concurrency 2`
  - `cd /home/dinar/diplom/frontend && npm run typecheck`
  - `cd /home/dinar/diplom/frontend && npm run build`
  - `docker compose config`
- Load-test baseline зафиксирован:
  - 3/3 успешных заказа
  - API avg latency `37.74 ms`, p95 `55.87 ms`
  - WS delivered `6/6`, avg delay `30.77 ms`
- Закрыты задачи: `TASK-042`, `TASK-043`, `TASK-044`, `TASK-045`, `TASK-046`.
- Внешние prerequisites, которые не эмулируются локально, но подготовлены конфигом/документацией: реальный GitHub repository secrets для deploy workflow, VPS-домен и Let’s Encrypt issuance, production `TELEGRAM_BOT_TOKEN`.

## 2026-03-31 (сессия 10)

- По запросу собран новый плановый блок `Demo Contour V1` и `Commercial Contour V2`.
- В `tasks.json` добавлены задачи `TASK-047` ... `TASK-060` со статусом `pending`, зависимостями, acceptance criteria и test steps.
- Сохранён execution plan на 2 спринта: `docs/superpowers/plans/2026-03-31-demo-contour-v1.md`.
- Следующий исполнительный шаг по приоритету: `TASK-047` → реальный frontend auth bridge вместо demo-login.

## 2026-03-31 (сессия 11)

- Закрыт первый блок Demo Contour V1:
  - `TASK-047` — реальный frontend auth вместо demo-login
  - `TASK-048` — session bootstrap, refresh по cookie и logout
  - `TASK-049` — role-aware redirects, guards и скрытие меню
- Реализовано:
  - реальный login screen на `POST /api/v1/auth/login`
  - авторитетная гидрация пользователя через `GET /api/v1/auth/me`
  - центральный auth transport в `frontend/src/api/client.ts` с auto Bearer injection и 401 refresh-retry
  - bootstrap auth-сессии через refresh-cookie flow
  - logout с очисткой frontend store и backend cookie-session
  - role-aware стартовые маршруты:
    - `super_admin`, `franchisee` → `/dashboard`
    - `point_manager`, `staff` → `/orders` → `/queue`
  - русификация auth shell/meta и router-level error fallback
- Для корректной SPA-CSRF работы поправлен backend:
  - `csrf_token` теперь выставляется с `Path=/`
  - legacy path cleanup добавлен в logout
- Живая верификация пройдена:
  - `cd /home/dinar/diplom/frontend && npm run typecheck`
  - `cd /home/dinar/diplom/frontend && npm run build`
  - `curl -sS http://127.0.0.1:18000/health`
  - `POST /api/v1/auth/login` → `200`
  - `GET /api/v1/auth/me` → `200`
  - `POST /api/v1/auth/refresh` с cookie+csrf → `200`
  - `POST /api/v1/auth/logout` с cookie+csrf → `204`
  - `POST /api/v1/auth/refresh` после logout с обновлённым cookie jar → `401`
  - role logins:
    - `audit-manager@japonica.example.com / Manager1234!` → `200`
    - `staff@japonica.example.com / Staff1234!` → `200`
    - `franchisee-demo@japonica.example.com / Franchisee1234!` → `200`
- Tester-субагенты прогнаны:
  - первый runner подтвердил live auth flow и role logins
  - второй reviewer нашёл CSRF-path проблему и legacy demo-auth residue
  - после фикса recheck tester вернул `No findings`
- Временный аккаунт `franchisee-demo@japonica.example.com` создан через users API только для верификации блока; формализация demo-аккаунтов и полного сидинга остаётся в `TASK-055`.

## 2026-03-31 (сессия 12)

- Закрыт второй блок Demo Contour V1:
  - `TASK-050` — orders history/queue/status changes/WebSocket sync
  - `TASK-051` — warehouse screen, supply, adjustment, movements
  - `TASK-052` — dashboard + analytics/assistant binding для `super_admin` и `franchisee`
  - `TASK-053` — franchisee board/detail/notes/tasks/points
- Реализовано и доведено:
  - `staff` теперь может менять статусы заказов на backend, как и ожидалось от queue-flow
  - `OrderHistoryPage` и `OrderQueuePage` синхронизируются с live-событиями и не падают на пустых/error сценариях
  - warehouse UI реально работает с backend: видны ингредиенты, остатки, приход, корректировка и история движений
  - общая tenant-модель точек унифицирована через backend contract, чтобы `/points` и analytics одинаково считали доступ
  - `DashboardPage` и `AIAssistantPage` переведены на section-level degraded/loading handling вместо all-or-nothing
  - `FranchiseeKanbanPage` теперь тянет real detail, умеет создавать/привязывать точки и показывает query errors вместо ложной пустоты
- По ходу блока устранены найденные дефекты:
  - исправлен PostgreSQL crash на `GET /points` для point-scoped ролей: дедупликация точек переведена на `Point.id`, без `DISTINCT` по JSON-колонке
  - `GET /api/v1/warehouse/audit` теперь возвращает `422` на битую дату вместо `500`
  - в franchisee board progress больше не обнуляется целиком при единичном падении `/tasks`, используется `Promise.allSettled`
- Живая верификация пройдена:
  - `cd /home/dinar/diplom/frontend && npm run typecheck`
  - `cd /home/dinar/diplom/frontend && npm run build`
  - `PYTHONPYCACHEPREFIX=/tmp/codex-pyc python3 -m py_compile backend/app/modules/orders/router.py backend/app/modules/warehouse/router.py backend/app/modules/warehouse/schemas.py backend/app/modules/warehouse/service.py backend/app/modules/analytics/service.py backend/app/modules/points/router.py backend/app/modules/franchisee/service.py`
  - `curl -sS http://127.0.0.1:18000/health`
  - order flow on point `298201e8-899f-4aca-86b3-dc02762439d2`:
    - `POST /api/v1/orders` → `201`
    - WebSocket delivered `order_created`
    - `PATCH /api/v1/orders/{id}/status` под `staff` → `200`
    - WebSocket delivered `order_status_changed`
  - warehouse flow под `point_manager`:
    - `GET /warehouse/ingredients`
    - `POST /warehouse/stock/supply`
    - `GET /warehouse/stock`
    - `POST /warehouse/stock/movements` with `adjustment`
    - `GET /warehouse/stock/movements`
  - analytics flow:
    - `super_admin` видит сетевую выручку по `8` точкам
    - `franchisee-demo` видит только `1` точку
    - `assistant/chat` отвечает в fallback режиме с `evidence`
  - franchisee flow:
    - `POST /franchisees`
    - `PATCH /franchisees/{id}/stage`
    - `POST /franchisees/{id}/tasks`
    - `POST /franchisees/{id}/notes`
    - `POST /franchisees/{id}/points`
    - `GET detail/tasks/notes/points` согласованы
- Tester-субагенты прогнаны:
  - reviewer по `TASK-052` вернул `No findings`
  - reviewer по `TASK-053` нашёл 2 medium issue, после фикса recheck подтвердил их закрытие
  - reviewer по `TASK-050/051` нашёл 1 medium issue в `warehouse/audit`, после фикса recheck подтвердил закрытие
- Для demo-верификации временно привязаны к точке `Audit Point Allowed`:
  - `staff@japonica.example.com`
  - `franchisee-demo@japonica.example.com`
  - эти временные подготовительные данные будут нормализованы воспроизводимым seed-сценарием в `TASK-055`

## 2026-03-31 (сессия 13)

- Закрыт третий блок Demo Contour V1:
  - `TASK-054` — полная русификация demo-поверхности
  - `TASK-055` — безопасный и воспроизводимый demo seed
  - `TASK-056` — demo package: use cases, 7–10 минутный script, fallback и checklist
- По `TASK-054` доведена русская поверхность для комиссии:
  - убраны остаточные английские channel labels на dashboard/history
  - убраны raw websocket event names из UI
  - добавлен frontend mapping для provider/context labels в assistant
  - create modal на franchisee board получил русские `ok/cancel`
  - исправлены последние low-level хвосты (`Идентификатор точки`, `ИИ отключён`, безопасные fallback labels)
- По `TASK-055` подготовлен demo контур данных:
  - `backend/scripts/seed_demo.py`
  - `backend/scripts/verify_demo_seed.py`
  - фиксированные логины:
    - `admin@japonica.example.com / Admin1234!`
    - `franchisee-ufa1@japonica.example.com / Demo1234!`
    - `manager-ufa1@japonica.example.com / Demo1234!`
    - `staff-ufa1@japonica.example.com / Demo1234!`
  - seed безопасно обновляет demo root entities через merge и больше не удаляет non-demo stock/recipe связи из-за общих demo ingredients
  - в verify добавлен safety regression check через nested transaction
- По `TASK-056` собран пакет для показа:
  - `docs/demo/use-cases.md`
  - `docs/demo/presentation-script.md`
  - `docs/demo/fallback-script.md`
  - `docs/demo/checklist.md`
  - `README.md` обновлён и больше не утверждает, что frontend login демонстрационный
- Свежая верификация пройдена:
  - `cd /home/dinar/diplom/frontend && npm run typecheck`
  - `cd /home/dinar/diplom/frontend && npm run build`
  - `PYTHONPYCACHEPREFIX=/tmp/codex-pyc python3 -m py_compile backend/scripts/seed_demo.py backend/scripts/verify_demo_seed.py`
  - `docker compose exec -T api /workspace/.venv/bin/python backend/scripts/seed_demo.py`
  - повторный `docker compose exec -T api /workspace/.venv/bin/python backend/scripts/seed_demo.py`
  - `docker compose exec -T api /workspace/.venv/bin/python backend/scripts/verify_demo_seed.py`
  - `curl -I http://127.0.0.1:15173`
- Tester-субагенты прогнаны после каждой части блока:
  - по `TASK-054` сначала нашли остаточные английские строки, после фикса recheck вернул `No findings`
  - по `TASK-055` сначала нашли unsafe cleanup для stock/recipe связей, после фикса и regression-check recheck вернул `No findings`
  - по `TASK-056` reviewers нашли 3 документарные несостыковки, после правок оба финальных recheck вернули `No findings`

## 2026-03-31 (сессия 14)

- Закрыт блок V2 / commercial contour:
  - `TASK-057` — модель и API доступности блюд по каналам продаж
  - `TASK-058` — admin UI для блюд и каналов продаж
  - `TASK-059` — inbound-валидация по channel availability
  - `TASK-060` — интерактивный kanban очереди заказов с drag-and-drop
- По `TASK-057/059` реализовано:
  - `Dish.available_channels` с миграцией `20260331_0007_add_dish_sales_channels`
  - warehouse API читает и обновляет каналы продаж блюда
  - public inbound schema теперь принимает только `website/mobile_app/telegram/vk`
  - inbound path нормализует `dish_id/name` в канонический `OrderItem`
  - добавлена защита от `dish_identity_mismatch`
  - write-off теперь сначала резолвит блюдо по `dish_id`, затем fallback по `name`
- По `TASK-058` реализовано:
  - отдельная страница `/dishes` для `super_admin`
  - CRUD-lite по блюдам, фильтр active/inactive/all
  - редактирование `available_channels`, `is_active`, `price`, `description`
  - просмотр техкарты блюда
  - цена в русской UI теперь корректно принимает `123,45`, а не превращает её в `12345`
- По `TASK-060` реализовано:
  - desktop drag-and-drop для допустимых переходов статусов
  - mobile/button fallback сохранён
  - board больше не блокируется overlay-спиннером при background refetch
  - `pendingOrderIds` заменил одиночный `loadingOrderId`
  - после успешного `PATCH` делается optimistic update queue cache
  - drag автоматически сбрасывается, если order уже обновился через WS/polling
- Свежая верификация пройдена:
  - `docker compose -f /home/dinar/diplom/docker-compose.yml restart api && sleep 6 && curl -sS http://127.0.0.1:18000/health`
  - `docker compose -f /home/dinar/diplom/docker-compose.yml exec -T api /workspace/.venv/bin/python backend/scripts/verify_dish_channels.py`
  - `cd /home/dinar/diplom/frontend && npm run typecheck`
  - `cd /home/dinar/diplom/frontend && npm run build`
  - live smoke:
    - `POST /api/v1/auth/login` → `200`
    - `GET /api/v1/warehouse/dishes` → `200`, `23` dishes
    - `GET /api/v1/points` → `200`, `12` points
    - `GET /api/v1/orders?point_id=432441ef-5261-4759-b686-d0fff866ce9c` → `200`, `17` orders
- Tester-субагенты прогнаны по блоку:
  - backend reviewer сначала нашёл bypass через `dish_id/name mismatch`, отсутствие cleanup-safe verify и лишний `pos` в inbound schema; после фикса финальный recheck вернул `No findings`
  - dishes reviewer сначала нашёл UI-расхождения по `available_channels`, `price > 0` и потом locale bug с ценой `123,45`; после фиксов финальный recheck вернул `No findings`
  - queue reviewer сначала нашёл race-condition вокруг stale board после refetch failure и stale `dragState`; после optimistic update и drag revalidation финальный recheck вернул `No findings`

## 2026-03-31 (сессия 15)

- Исправлен критический demo-блокер на frontend login.
- Root cause:
  - frontend работал на `127.0.0.1:15173` через Vite dev server
  - `VITE_API_BASE_URL=/api`, но в `frontend/vite.config.ts` не был настроен `server.proxy`
  - из-за этого `POST /api/v1/auth/login` уходил в сам Vite и получал `404`, хотя backend endpoint был живой
- Исправление:
  - в `frontend/vite.config.ts` добавлен proxy `/api -> http://api:8000`
  - proxy target вынесен в `VITE_API_PROXY_TARGET` с default `http://api:8000`
  - перезапущен frontend-контейнер
- Проверка:
  - `POST http://127.0.0.1:15173/api/v1/auth/login` → `200`
  - прямой `POST http://127.0.0.1:18000/api/v1/auth/login` → `200`
  - `docker compose ps` остаётся healthy

## 2026-03-31 (сессия 16)

- Sprint 1 разбит по `prompt_от_PRD_до_tasks.md`, в `tasks.json` уже были добавлены `TASK-061..082`; по фактической верификации переведены в `done`:
  - `TASK-062` `TASK-064` `TASK-070` `TASK-071` `TASK-072` `TASK-073` `TASK-082`
- Работа велась параллельно через 4 субагента:
  - Documents backend
  - Kanban backend
  - Frontend Documents + Kanban
  - Telegram/mock notifications
- Что интегрировано в кодовую базу:
  - модуль `documents` с private storage, audit log, RBAC и API загрузки/скачивания
  - модуль `kanban` с досками, колонками, карточками, history, comments, custom fields и attachments через Documents
  - outbox `domain_events` + Celery beat `process_outbox_events`
  - frontend-страницы `/documents`, `/kanban`, `/kanban/:boardId` и пункты меню
  - Telegram mock-команды `/orders`, `/order`, `/tasks`, `/stock`, `/stock_add`, `/low_stock`; `/start` теперь отдаёт inline keyboard
  - `README.md` дополнен разделами `Documents v1` и `Kanban v1`
- Дополнительные исправления по интеграции:
  - `kanban custom_fields.options` расширен до произвольного JSON, чтобы принимать массивы для `select`
  - `nginx/default.conf` поднят до `client_max_body_size 55m` под лимит файлов 50 MB
  - `documents` публикует outbox-события `document.uploaded`, `document.downloaded`, `document.deleted`
- Верификация:
  - `UV_PROJECT_ENVIRONMENT=/tmp/diplom-uv-env uv run ruff check backend/app/core/telegram.py backend/app/modules/notifications backend/app/main.py backend/app/celery_app.py backend/app/worker.py backend/app/core/events.py backend/app/core/storage.py backend/app/db/models.py backend/app/modules/documents backend/app/modules/kanban backend/tests/test_kanban_service.py`
  - `UV_PROJECT_ENVIRONMENT=/tmp/diplom-uv-env uv run pytest backend/app/modules/notifications/test_telegram_service.py backend/tests/test_documents_storage.py backend/tests/test_documents_validation.py backend/tests/test_kanban_service.py -q`
  - `docker compose config`
  - `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/japonica_crm UV_PROJECT_ENVIRONMENT=/tmp/diplom-uv-env uv run alembic upgrade head`
  - `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/japonica_crm UV_PROJECT_ENVIRONMENT=/tmp/diplom-uv-env uv run python backend/scripts/export_openapi.py --output docs/openapi.json`
  - `cd frontend && npm run typecheck`
  - `cd frontend && npm run build`
  - live smoke по `kanban + documents`:
    - login → `200`
    - create board/columns → `201`
    - reorder columns → `200`
    - create card/move/history/comment/custom field/attachment → `200/201`
    - `GET /documents` + `GET /documents/{id}/download` + `GET /documents/audit-log` → `200`
    - итог smoke: `history_entries=1`, `custom_field_values=1`, `documents_count=1`, `audit_count=2`
- Оставлено в `pending` сознательно:
  - frontend manual QA задачи `TASK-068`, `TASK-069`, `TASK-075`, `TASK-076`, `TASK-077`
  - уведомления и Telegram end-to-end без отдельного acceptance-прогона `TASK-074`, `TASK-078`
  - отдельные test packs `TASK-080`, `TASK-081`

## 2026-03-31 (сессия 17)

- Доведён backend-пакет вокруг уведомлений, Telegram mock и test coverage Sprint 1.
- Закрыты по свежей верификации:
  - `TASK-074` — kanban notifications
  - `TASK-068` — documents page
  - `TASK-069` — documents audit viewer
  - `TASK-075` — kanban boards page
  - `TASK-076` — kanban board page with drag-and-drop
  - `TASK-077` — card drawer/details
  - `TASK-078` — Telegram mock commands
  - `TASK-080` — documents RBAC/validation tests
  - `TASK-081` — kanban CRUD/comments/custom fields/attachments tests
- Production-правки:
  - `backend/app/modules/kanban/service.py`
    - `list_boards()` теперь возвращает `card_count`
    - `create_card()` и `update_card()` планируют Celery notification tasks на assignee/deadline
  - `backend/app/modules/kanban/tasks.py`
    - добавлен alias task `send_card_deadline_set_notification`
    - тексты уведомлений включают название карточки, доски и срок
    - при отсутствии `telegram_chat_id` пишется `WARNING`, уведомление пропускается
  - `backend/app/modules/notifications/service.py`
    - `/start` теперь явно приветствует пользователя
    - `/orders` отдаёт до 10 заказов вместо 8
  - frontend:
    - `frontend/src/pages/KanbanBoardsPage.tsx` показывает `card_count`
    - `frontend/src/pages/KanbanBoardPage.tsx` получил inline-редактирование заголовка карточки в drawer
- Добавлены/обновлены тесты:
  - `backend/tests/test_documents_rbac.py`
  - `backend/tests/test_documents_validation.py`
  - `backend/tests/test_kanban_notifications.py`
  - `backend/tests/test_kanban_boards.py`
  - `backend/tests/test_kanban_cards.py`
  - `backend/tests/test_kanban_extras.py`
- Верификация:
  - `UV_PROJECT_ENVIRONMENT=/tmp/diplom-uv-env uv run pytest backend/app/modules/notifications/test_telegram_service.py backend/tests/test_documents_rbac.py backend/tests/test_documents_validation.py backend/tests/test_kanban_notifications.py backend/tests/test_kanban_boards.py backend/tests/test_kanban_cards.py backend/tests/test_kanban_extras.py backend/tests/test_kanban_service.py -q`
    - `31 passed in 0.81s`
  - `UV_PROJECT_ENVIRONMENT=/tmp/diplom-uv-env uv run ruff check backend/app/modules/notifications backend/app/modules/kanban backend/tests/test_documents_rbac.py backend/tests/test_documents_validation.py backend/tests/test_kanban_notifications.py backend/tests/test_kanban_boards.py backend/tests/test_kanban_cards.py backend/tests/test_kanban_extras.py backend/tests/test_kanban_service.py`
    - `All checks passed!`
  - `cd frontend && npm run typecheck`
  - `cd frontend && npm run build`
  - static acceptance сверка по frontend:
    - routes `/documents`, `/kanban`, `/kanban/:boardId` подключены
    - sidebar roles содержит `Документы` и `Канбан`
    - `DocumentsPage` содержит upload drag-and-drop, filters, download, delete, audit tab
    - `KanbanBoardsPage` содержит create/delete/navigate/card_count
    - `KanbanBoardPage` содержит `DndContext`, card counter, drawer sections `Комментарии`, `Вложения`, `Кастомные поля`, `История`, inline title edit
  - live smoke:
    - `GET /kanban/boards` возвращает `card_count`
    - `PUT /kanban/cards/{id}` с новым `deadline` → `200`
    - helper smoke для Telegram parser/start text:
      - callback `orders` распознаётся
      - `/tasks` распознаётся
      - текст `/start` содержит приветствие
  - service-level Telegram smoke на реальной БД для `manager-ufa1@japonica.example.com`:
    - `/start` → inline keyboard
    - `/orders` → список заказов точки
    - `/order {id} {next_status}` → статус обновлён
    - `/tasks` → активная kanban-карточка с deadline/priority
    - `/stock` → реальные остатки
    - `/stock_add {ingredient_id} 1.250` → приход отражён в ответе
    - `/low_stock` → корректный ответ по порогам

## 2026-03-31 (сессия 17)

- Закрыл `TASK-080` тестами для Documents без правок production-кода.
- Добавлено:
  - [backend/tests/test_documents_rbac.py](/home/dinar/diplom/backend/tests/test_documents_rbac.py) с 8 unit-level кейсами на `super_admin`, `franchisee`, `point_manager`, `staff`
  - [backend/tests/test_documents_validation.py](/home/dinar/diplom/backend/tests/test_documents_validation.py) с кейсом на `bad extension` (`.exe`)
- Подход:
  - RBAC проверяется напрямую через `backend.app.modules.documents.service.ensure_document_action_allowed`
  - для веток scope использован `monkeypatch` внутренних helper'ов `_get_entity_scope`, `_task_belongs_to_franchisees`, `_card_is_visible_for_user`
- Верификация:
  - `UV_PROJECT_ENVIRONMENT=/tmp/diplom-uv-env uv run pytest backend/tests/test_documents_rbac.py backend/tests/test_documents_validation.py -q`
  - результат: `12 passed in 0.49s`
  - `UV_PROJECT_ENVIRONMENT=/tmp/diplom-uv-env uv run ruff check backend/tests/test_documents_rbac.py backend/tests/test_documents_validation.py`
  - результат: `All checks passed!`
- Статус:
  - `TASK-080` переведён в `done`
