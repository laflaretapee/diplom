# Demo Contour V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Собрать demo-ready связанный продукт: реальный frontend auth, рабочие CRUD/flows на frontend, сиды, русская поверхность и сценарии показа.

**Architecture:** Backend уже содержит реальные auth, orders, warehouse, franchisee и analytics endpoints. Основная проблема не в сервере, а в том, что frontend частично живёт на demo-auth и смешивает реальный UI с макетными сценариями. План делит работу на 2 спринта: сначала Demo Contour V1 для показа, затем коммерческий контур продаж блюд по каналам и drag-and-drop kanban.

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL, React, Zustand, React Query, Ant Design, WebSocket, Celery, Redis.

---

## File Map

**Frontend auth and routing**
- Modify: `frontend/src/pages/LoginPage.tsx`
- Modify: `frontend/src/auth/store.ts`
- Modify: `frontend/src/auth/types.ts`
- Modify: `frontend/src/components/RequireAuth.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/api/client.ts`
- Create or modify: `frontend/src/auth/session.ts` or equivalent bootstrap helper

**Data bridge**
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/pages/OrderHistoryPage.tsx`
- Modify: `frontend/src/pages/OrderQueuePage.tsx`
- Modify: `frontend/src/pages/WarehousePage.tsx`
- Modify: `frontend/src/pages/FranchiseeKanbanPage.tsx`
- Modify: `frontend/src/pages/AIAssistantPage.tsx` (only if stable enough)
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/auth/roleMeta.ts`

**Demo content**
- Create or modify: `backend/scripts/seed_demo_data.py`
- Modify: `backend/scripts/seed_admin.py` if reused
- Create: `docs/demo/use-cases.md`
- Create: `docs/demo/presentation-script.md`
- Create: `docs/demo/fallback-script.md`

**Commercial contour V2**
- Modify: `backend/app/models/dish.py`
- Modify: `backend/app/modules/warehouse/schemas.py`
- Modify: `backend/app/modules/warehouse/router.py`
- Modify: `backend/app/modules/warehouse/service.py`
- Modify: `backend/app/modules/inbound/service.py`
- Create or modify: `frontend/src/pages/DishesPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/pages/OrderQueuePage.tsx`

---

## Sprint Breakdown

### Sprint 1: Demo Contour V1

**Critical path**
- `TASK-047` Frontend real auth integration
- `TASK-048` Session bootstrap + refresh + logout
- `TASK-049` Role-based route guards and redirects
- `TASK-050` Orders page full API binding
- `TASK-051` Warehouse page full API binding + fix actions
- `TASK-052` Dashboard and analytics binding
- `TASK-053` Franchisee page final API binding
- `TASK-054` RU localization of demo surface
- `TASK-055` Demo seed script
- `TASK-056` Demo use cases + presentation script

**Expected output of Sprint 1**
- Комиссия видит реальную систему, а не demo-shell.
- Есть воспроизводимый набор аккаунтов и данных.
- Есть 4–5 рабочих use cases без ручных API-запросов.

### Sprint 2: Commercial Contour V2

**Focus**
- `TASK-057` Dish sales channels model + API
- `TASK-058` Dish sales channels UI
- `TASK-059` Inbound validation by channel availability
- `TASK-060` Interactive kanban DnD

**Expected output of Sprint 2**
- CRM управляет не только блюдами и техкартами, но и доступностью в каналах продаж.
- Очередь заказов становится по-настоящему интерактивной для операционного персонала.

---

## Dependency Order

### Phase A: Auth Bridge
- `TASK-047` -> `TASK-048` -> `TASK-049`

### Phase B: Data Bridge
- `TASK-050`
- `TASK-051`
- `TASK-052`
- `TASK-053`

### Phase C: Demo Content
- `TASK-054`
- `TASK-055`
- `TASK-056`

### Phase D: Commercial Follow-up
- `TASK-057` -> `TASK-058`
- `TASK-057` -> `TASK-059`
- `TASK-050` -> `TASK-060`

---

## Task Notes

### TASK-047 Frontend real auth integration
- Replace demo login with real `POST /api/v1/auth/login`.
- Store access token in Zustand only, not in localStorage.
- Immediately call `GET /api/v1/auth/me` after login to populate role and name.
- UI outcome:
  - `super_admin`, `franchisee` -> `/dashboard`
  - `point_manager`, `staff` -> `/orders/history` or `/queue` depending on chosen entrypoint

### TASK-048 Session bootstrap + refresh + logout
- On app bootstrap:
  - try `GET /api/v1/auth/me` if access token is in memory
  - otherwise try `POST /api/v1/auth/refresh` using refresh cookie + CSRF cookie flow
- Handle expired access token centrally in `apiClient`.
- On logout:
  - send `POST /api/v1/auth/logout`
  - clear store
  - redirect to `/login`

### TASK-049 Role guards and redirects
- Replace generic guard with role-aware route access.
- Hide menu items that should not be visible.
- Ensure manual URL opening is redirected safely.

### TASK-050 Orders full API binding
- Bind `OrderHistoryPage` and `OrderQueuePage` to real auth/session.
- Fix start route for `point_manager` and `staff`.
- Preserve WebSocket updates and status mutations.
- Add strong empty/error states in Russian.

### TASK-051 Warehouse full API binding
- Ensure `WarehousePage` uses real auth, selected point, supply and adjustment mutations.
- Add clearer validation and mutation success states.
- Verify one real demo-flow:
  - open stock
  - create supply
  - create adjustment
  - see movement history
  - show low-stock

### TASK-052 Dashboard and analytics binding
- Keep AI optional, not critical path.
- Dashboard must be stable even if assistant is disabled or degraded.
- Summary, revenue, channels, top dishes should work for `super_admin` and `franchisee`.

### TASK-053 Franchisee final API binding
- Use existing board/detail/tabs as the main demo surface.
- No drag-and-drop in V1.
- Ensure stage change, notes, tasks and points work with real auth.

### TASK-054 RU localization
- Translate all commission-visible strings:
  - login
  - shell and sidebar
  - dashboard
  - orders
  - warehouse
  - franchisee
  - analytics or assistant
  - empty, loading, success, error states

### TASK-055 Demo seed script
- Seed fixed accounts:
  - `admin@japonica.example.com`
  - `manager-ufa1@japonica.example.com`
  - `staff-ufa1@japonica.example.com`
  - `franchisee-demo@japonica.example.com`
- Seed fixed password for demo stand.
- Seed:
  - 2–3 points
  - 8–15 ingredients
  - 6–10 dishes
  - 10–20 orders across statuses
  - 1–3 franchisees across stages
  - enough historical orders for analytics

### TASK-056 Demo package
- Prepare 5 demo use cases:
  - operator processes order
  - stock is written off and replenished
  - super_admin sees network analytics
  - franchisee onboarding pipeline
  - AI assistant as final bonus
- Prepare 7–10 minute route and fallback script.

### TASK-057..060 Next Sprint
- V2 focuses on channel assortment and DnD kanban only after V1 is stable.
- Do not pull V2 work into V1 unless V1 critical path is green.

---

## Verification Checklist Before Demo

- [ ] Real frontend login works for `super_admin`, `franchisee`, `point_manager`, `staff`
- [ ] Reload keeps session alive through refresh cookie flow
- [ ] Logout fully clears session
- [ ] Point manager can process a real order end-to-end
- [ ] Warehouse supply and adjustment work from UI
- [ ] Movements and low-stock are visible
- [ ] Dashboard loads real summary and revenue data
- [ ] Franchisee board opens and updates stage correctly
- [ ] Main UI surface is in Russian
- [ ] Demo seed script recreates full data set
- [ ] AI assistant is either stable or explicitly moved to “optional bonus”
- [ ] Fallback route exists if WS or AI misbehave

---

## Working Use Cases Expected After Sprint 1

1. Менеджер точки входит в систему и проводит заказ по статусам.
2. Менеджер показывает склад, приход, корректировку и движения.
3. Super_admin показывает network dashboard и аналитику.
4. Super_admin показывает pipeline франчайзи и меняет стадию.
5. В конце можно показать AI assistant как дополнительный слой.

---

## Immediate Execution Order

1. Start with `TASK-047`.
2. Do not touch seeds before auth bridge is green.
3. Do not expand dishes sales channels until `TASK-056` is complete.

