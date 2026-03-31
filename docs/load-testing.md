# TASK-046 Load Testing

This document records the baseline load-test for order creation and websocket fan-out.

## How to run

```bash
python backend/scripts/loadtest_orders_ws.py
```

Optional env overrides:

- `API_BASE_URL`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `LOADTEST_WS_CLIENTS`
- `LOADTEST_ORDERS`
- `LOADTEST_CONCURRENCY`
- `LOADTEST_ORDER_DELAY_MS`
- `LOADTEST_ITEM_COUNT`
- `LOADTEST_ITEM_PRICE`
- `LOADTEST_ITEM_NAME`
- `LOADTEST_SOURCE_CHANNEL`
- `LOADTEST_PAYMENT_TYPE`
- `LOADTEST_NO_AUTO_DETECT_PAYMENT_TYPE`
- `LOADTEST_REPORT_PATH`

## Baseline Results

- Run timestamp: 2026-03-31 02:16:01 +05
- API base URL: `http://127.0.0.1:18080/api/v1`
- Point: `AI Point 4156e5` (`432441ef-5261-4759-b686-d0fff866ce9c`)
- Admin: `admin@japonica.example.com`
- WS clients: `2`
- Orders attempted: `5`
- Orders succeeded: `5`
- Orders failed: `0`
- Runtime: `1.87s`

## Metrics

| Metric | Value |
| --- | ---: |
| Successful requests | 5 |
| Failed requests | 0 |
| API avg latency (ms) | 33.06 |
| API max latency (ms) | 65.55 |
| API approx p95 latency (ms) | 62.23 |
| WS delivered events | 10 |
| WS expected events | 10 |
| WS avg delivery delay (ms) | 31.74 |
| WS max delivery delay (ms) | 63.67 |
| WS approx p95 delivery delay (ms) | 63.62 |

## Bottlenecks To Check

- DB commit time in `POST /orders`
- Background `write_off_for_order` tasks
- Broadcast fan-out in `ws_manager.broadcast`
- WS readiness and client count under concurrency

## Raw Notes

- Payment type used: `cash`
- Probe order id: `c8c7ac1b-99f3-4ce5-9e1d-a1945a5417b4`
- Probe payment type: `cash`
- Probe order excluded from the throughput totals above.
