# Current Check Scenarios

Дата фиксации: `2026-03-31`

## URL

- Frontend: `http://127.0.0.1:15173`
- API Swagger: `http://127.0.0.1:18000/docs`
- API health: `http://127.0.0.1:18000/health`
- Nginx health: `http://127.0.0.1:18080/health`

## Демо-аккаунты

| Роль | Логин | Пароль | Базовый маршрут |
| --- | --- | --- | --- |
| `super_admin` | `admin@japonica.example.com` | `Admin1234!` | `/dashboard` |
| `franchisee` | `franchisee-ufa1@japonica.example.com` | `Demo1234!` | `/dashboard` |
| `point_manager` | `manager-ufa1@japonica.example.com` | `Demo1234!` | `/queue` |
| `staff` | `staff-ufa1@japonica.example.com` | `Demo1234!` | `/queue` |

## Что я реально прогнал сейчас

### Стек и health

- `docker compose ps`: все сервисы `Up` и `healthy`
- `GET /health` на API: `{"status":"ok"}`
- `GET /health` на nginx: `ok`

### API smoke

Прогон выполнен по реальному API и БД. Итог:

```json
{
  "logins_ok": ["super_admin", "franchisee", "point_manager", "staff"],
  "point_name": "[DEMO] Ufa 1",
  "order_status_transition": "ready->delivered",
  "ingredients_count": 29,
  "stock_count": 13,
  "supply_new_quantity": "5.000",
  "movements_count": 25,
  "audit_count": 25,
  "revenue_points": 12,
  "dishes_top_count": 5,
  "dishes_bottom_count": 5,
  "channels_count": 4,
  "summary_keys": ["pending_orders", "top_dish_today", "total_orders_today", "total_revenue_today"],
  "forecast_items": 11,
  "anomalies_signals": 2,
  "franchisee_company": "[DEMO] Ufa Family Franchise",
  "franchisee_tasks": 2,
  "franchisee_notes": 1,
  "franchisee_points": 2,
  "kanban_board_id": "d0b59a9c-595b-428f-bb8b-95d03e2ef37d",
  "kanban_card_id": "c9fed426-6bf1-44e3-a52c-3e95ac6fe388",
  "attachment_document_id": "63ca4b63-ac64-46eb-b81d-d64d54e394fe",
  "documents_audit_actions": ["delete", "download", "upload"]
}
```

### Telegram mock smoke

Прогон выполнен через сервисный слой и реальную БД, без обращения во внешний Telegram API.

```json
{
  "messages_sent": 7,
  "start_has_keyboard": true,
  "orders_preview": [
    "Последние заказы:",
    "• #381A98A8 | [DEMO] Ufa 1 | new | 199 ₽"
  ],
  "order_update_preview": "Статус заказа #381A98A8 обновлён: in_progress.",
  "tasks_preview": [
    "Задачи из kanban:",
    "• Smoke card 20260331165309 ([SMOKE] Current Check 20260331165309 / In Progress; priority high; deadline 2026-04-01)"
  ],
  "stock_preview": [
    "Остатки по складу:",
    "• [DEMO] Ufa 1: AI Rice 4156e5 5 kg (min 5)"
  ],
  "stock_add_preview": "Остаток обновлён: AI Rice 4156e5 +1.25 kg на точке [DEMO] Ufa 1. Новый остаток: 6.25 kg.",
  "low_stock_preview": [
    "Позиции ниже минимального остатка не найдены."
  ]
}
```

## Что можно проверить вручную прямо сейчас

### 1. Базовая доступность

1. Открой `http://127.0.0.1:15173`.
2. Проверь вход под всеми четырьмя ролями.
3. Убедись, что происходит role-based redirect:
   `admin` -> `/dashboard`, `manager` -> `/queue`, `staff` -> `/queue`, `franchisee` -> `/dashboard`.

### 2. Очередь заказов и история

Роль: `point_manager`

1. Войти как `manager-ufa1@japonica.example.com`.
2. Открыть `/queue`.
3. Убедиться, что список заказов точки `[DEMO] Ufa 1` доступен.
4. Открыть `/orders/history`.
5. Проверить, что изменения статуса отражаются в истории.

Примечание:
автоматический smoke сейчас провёл переход одного заказа `ready -> delivered`.

### 3. Склад

Роль: `point_manager`

1. Открыть `/warehouse`.
2. Проверить остатки и движения по точке `[DEMO] Ufa 1`.
3. Проверить audit trail по складу.
4. При необходимости сделать приход и убедиться, что история движений обновилась.

Примечание:
автоматический smoke создал приход, после него `new_quantity = 5.000` для одной из позиций.

### 4. Аналитика и dashboard

Роль: `super_admin`

1. Открыть `/dashboard`.
2. Проверить summary-метрики.
3. Через UI или Swagger проверить:
   `/analytics/revenue`, `/analytics/dishes`, `/analytics/channels`, `/analytics/forecast`, `/analytics/anomalies`.

Подтверждено автоматикой:

- `revenue_points = 12`
- `top/bottom dishes` вернулись по 5 позиций
- `channels_count = 4`
- `forecast_items = 11`
- `anomalies_signals = 2`

### 5. Контур франчайзи

Роли: `super_admin`, `franchisee`

1. Под `admin` открыть `/franchisee`.
2. Найти карточку `[DEMO] Ufa Family Franchise`.
3. Проверить задачи, заметки и привязанные точки.
4. Перелогиниться под `franchisee-ufa1@japonica.example.com`.
5. Убедиться, что доступен только свой контур.

Подтверждено автоматикой:

- `franchisee_tasks = 2`
- `franchisee_notes = 1`
- `franchisee_points = 2`

### 6. Documents

Роль: `super_admin`

1. Открыть `/documents`.
2. Проверить вкладку со списком документов.
3. Загрузить новый `.txt` или `.pdf`.
4. Скачать файл.
5. Удалить файл.
6. Открыть вкладку журнала и убедиться, что видны `upload`, `download`, `delete`.

Подтверждено автоматикой:

- upload -> download -> delete прошли на реальном API
- в audit log зафиксированы действия `delete`, `download`, `upload`

### 7. Kanban

Роль: `point_manager`

1. Открыть `/kanban`.
2. Найти доску `[SMOKE] Current Check 20260331165309`.
3. Открыть доску и проверить две колонки:
   `To Do`, `In Progress`.
4. Открыть карточку `Smoke card 20260331165309`.
5. Проверить комментарий, историю, кастомное поле и вложение.
6. Попробовать перетащить карточку между колонками.

Готовые артефакты после smoke:

- board id: `d0b59a9c-595b-428f-bb8b-95d03e2ef37d`
- card id: `c9fed426-6bf1-44e3-a52c-3e95ac6fe388`
- attachment document id: `63ca4b63-ac64-46eb-b81d-d64d54e394fe`

Подтверждено автоматикой:

- создание доски
- создание колонок
- reorder колонок
- создание карточки
- комментарий
- кастомное поле
- move карточки
- history
- attachment upload

### 8. Telegram mock

Проверка зависит от привязанного Telegram-аккаунта и webhook-контура.

Команды, которые подтверждены сервисным smoke:

- `/start`
- `/orders`
- `/order <uuid> <status>`
- `/tasks`
- `/stock`
- `/stock_add <ingredient_id> <qty>`
- `/low_stock`

Ожидаемые эффекты:

- `/start` показывает главное меню с inline keyboard
- `/orders` возвращает последние заказы
- `/order` меняет статус заказа
- `/tasks` показывает активные kanban-карточки
- `/stock` показывает остатки
- `/stock_add` отражает новый остаток
- `/low_stock` показывает позиции ниже минимума или сообщение об их отсутствии

### 9. AI Assistant

Это бонусный сценарий. Он не входил в текущий обязательный smoke, потому что зависит от AI-провайдера.

Если хочешь проверить его вручную:

1. Войти под `super_admin`.
2. Открыть `/assistant`.
3. Задать вопрос по аналитике точки.

Если отвечает нестабильно, это ожидаемый fallback-сценарий для демо, а не блокер для основного контура.

## Известная оговорка

Старые standalone-скрипты:

- `backend/scripts/verify_orders.py`
- `backend/scripts/verify_warehouse.py`

сейчас не являются надёжным источником smoke-проверки: они падают на mapper/import проблеме вокруг `Franchisee` при инициализации моделей. Поэтому для этой фиксации я использовал живой HTTP smoke по API и отдельный service-level smoke для Telegram.
