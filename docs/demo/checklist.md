# Demo Checklist

## За 10–15 минут до показа

1. Убедиться, что стек поднят:

```bash
docker compose up -d
docker compose ps
```

2. Пересоздать demo-данные:

```bash
docker compose exec -T api /workspace/.venv/bin/python backend/scripts/seed_demo.py
docker compose exec -T api /workspace/.venv/bin/python backend/scripts/verify_demo_seed.py
```

3. Проверить frontend и API:

```bash
curl -I http://127.0.0.1:15173
curl -sS http://127.0.0.1:18000/health
curl -sS http://127.0.0.1:18080/health
```

4. Открыть заранее:

- frontend: `http://127.0.0.1:15173`
- swagger: `http://127.0.0.1:18000/docs`
- при необходимости nginx API: `http://127.0.0.1:18080/api/v1`

## Быстрый smoke check

- `super_admin` логин работает
- `manager-ufa1` логин работает
- `franchisee-ufa1` логин работает
- `/dashboard` открывается
- `/queue` открывается
- `/warehouse` открывается
- `/franchisee` открывается

## Demo Accounts

- `admin@japonica.example.com / Admin1234!`
- `franchisee-ufa1@japonica.example.com / Demo1234!`
- `manager-ufa1@japonica.example.com / Demo1234!`
- `staff-ufa1@japonica.example.com / Demo1234!`

## Основной маршрут

1. Вход под `admin`
2. Dashboard
3. Вход под `manager-ufa1`
4. Queue
5. Warehouse
6. Вход под `admin`
7. Franchisee board
8. AI assistant как бонус

## Если что-то идёт не так

- WebSocket капризничает: перейти на `/orders/history` и показать ручной refresh
- AI не отвечает: пропустить `/assistant`, усилить показ аналитикой
- Нет времени: использовать сокращённый маршрут из `docs/demo/fallback-script.md`

## Что держать открытым в заметках

- `docs/demo/use-cases.md`
- `docs/demo/presentation-script.md`
- `docs/demo/fallback-script.md`
