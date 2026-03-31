# Demo Seed Design

**Goal:** Add a reproducible, idempotent, safe demo seed for the backend that creates fixed demo accounts and enough owned demo data to drive analytics, warehouse, and franchisee routes without touching unrelated dev data.

## Scope

The work is limited to backend seed and verification scripts plus minimal safe adjacent support if strictly needed. No frontend changes are allowed.

## Ownership Strategy

The seed owns only a tagged demo contour:

- Fixed demo user emails:
  - `admin@japonica.example.com`
  - `franchisee-ufa1@japonica.example.com`
  - `manager-ufa1@japonica.example.com`
  - `staff-ufa1@japonica.example.com`
- Tagged names for points, ingredients, dishes, and franchisees using a stable demo prefix.
- Deterministic UUIDs for demo entities so repeated runs converge to the same graph.
- Cleanup only for dependent rows connected to owned demo entities:
  - `orders`
  - `user_points`
  - `dish_ingredients`
  - `stock_items`
  - `stock_movements`
  - `franchisee_tasks`

The seed must not globally delete or mutate unrelated data.

## Target Demo Dataset

The seed will create or normalize:

- 1 `super_admin`
- 1 `franchisee`
- 1 `point_manager`
- 1 `staff`
- 3 tagged demo points
- 10-12 tagged demo ingredients
- 8 tagged demo dishes plus recipe rows
- 16-18 orders across multiple statuses
- 3 franchisee cards in different stages
- franchisee tasks and notes
- point assignments for manager and staff
- stock items and movement history over 28 days

## Data Shape

### Users

Passwords use the existing bcrypt-compatible helper from `backend.app.core.security` rather than `passlib`.

### Franchisees and Points

Three franchisee records cover different stages such as `active`, `negotiation`, and `training`. Three points are attached across the owned franchisee contour so both admin and franchisee views have meaningful data.

### Warehouse

Ingredients and stock items are created for each point. Historical movements include supplies, order-related consumption, and a small amount of manual adjustment/writeoff activity so warehouse stock, movements, audit, procurement forecast, and anomaly calculations all return populated payloads.

### Dishes and Recipes

Tagged dishes are linked to tagged ingredients through `dish_ingredients`. Order payload items store both `dish_id` and human-readable names so analytics can aggregate correctly and forecast can resolve recipes.

### Orders and Time Windows

Order timestamps are generated relative to current UTC time across the last 28 days. The dataset intentionally includes:

- multiple orders today for dashboard summary
- orders in the last 7 and previous 7 day windows
- different source channels
- different statuses, including cancelled
- one point with lower recent revenue than the previous week
- one point with elevated manual writeoff/adjustment quantities

This makes `revenue`, `dishes`, `channels`, `summary`, `forecast`, and `anomalies` non-empty and meaningful.

## Script Design

### `backend/scripts/seed_demo.py`

Responsibilities:

- discover owned demo entities
- delete only owned dependent rows in child-to-parent order
- recreate the entire owned demo graph deterministically
- print a compact summary of created entities

The script should work directly against the configured async SQLAlchemy session and models.

### `backend/scripts/verify_demo_seed.py`

Responsibilities:

- verify fixed logins exist and authenticate
- verify required counts and key tagged entities in the database
- verify warehouse, analytics, and franchisee demo routes return populated payloads
- fail loudly with actionable messages if the API is unavailable or demo data is incomplete

The script accepts an optional base URL for environments where the API is not on the default local address.

## Error Handling

- Missing database connectivity should fail fast.
- Cleanup queries must be scoped to owned demo IDs only.
- Verify failures should identify the missing account, entity class, route, or payload field.

## Verification Strategy

Primary verification is script-driven:

1. run `seed_demo.py`
2. run `verify_demo_seed.py`
3. optionally inspect counts and route payloads for spot checks

This replaces ad hoc seed accumulation with a deterministic backend demo baseline.
