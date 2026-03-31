from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

import httpx
import websockets

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.modules.orders.schemas import OrderCreate, OrderItem  # noqa: E402
from backend.app.models.order import PaymentType, SourceChannel  # noqa: E402


DEFAULT_ADMIN_EMAIL = "admin@japonica.example.com"
DEFAULT_ADMIN_PASSWORD = "Admin1234!"
DEFAULT_API_BASE_URL = "http://127.0.0.1:8000/api/v1"
DEFAULT_ORDER_COUNT = 20
DEFAULT_WS_CLIENTS = 3
DEFAULT_CONCURRENCY = 5
DEFAULT_PAYMENT_TYPES = (PaymentType.CASH, PaymentType.CARD, PaymentType.ONLINE)


@dataclass(slots=True)
class LoadTestConfig:
    api_base_url: str
    admin_email: str
    admin_password: str
    ws_clients: int
    order_count: int
    concurrency: int
    order_delay_ms: int
    item_count: int
    item_price: Decimal
    item_name: str
    source_channel: SourceChannel
    payment_type: PaymentType | None
    auto_detect_payment_type: bool
    report_path: Path | None


@dataclass(slots=True)
class OrderAttempt:
    index: int
    order_id: str | None
    ok: bool
    status_code: int | None
    started_at: float | None
    latency_ms: float | None
    error: str | None = None


@dataclass(slots=True)
class WsEvent:
    client_id: int
    order_id: str
    received_at: float
    latency_ms: float


@dataclass(slots=True)
class RunSummary:
    config: LoadTestConfig
    admin_user: dict[str, Any]
    point_id: str
    point_name: str
    payment_type: str
    order_attempts: list[OrderAttempt]
    ws_events: list[WsEvent]
    ws_connected: int
    runtime_s: float
    probe_order_id: str | None = None
    probe_payment_type: str | None = None

    @property
    def successful_requests(self) -> int:
        return sum(1 for attempt in self.order_attempts if attempt.ok)

    @property
    def failed_requests(self) -> int:
        return sum(1 for attempt in self.order_attempts if not attempt.ok)

    @property
    def api_latencies_ms(self) -> list[float]:
        return [attempt.latency_ms for attempt in self.order_attempts if attempt.ok and attempt.latency_ms is not None]

    @property
    def ws_latencies_ms(self) -> list[float]:
        return [event.latency_ms for event in self.ws_events]

    @property
    def expected_ws_events(self) -> int:
        return self.config.ws_clients * self.successful_requests


def parse_args() -> LoadTestConfig:
    parser = argparse.ArgumentParser(
        description="Load-test order creation and websocket fan-out for TASK-046."
    )
    parser.add_argument("--api-base-url", default=os.getenv("API_BASE_URL", DEFAULT_API_BASE_URL))
    parser.add_argument("--admin-email", default=os.getenv("ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL))
    parser.add_argument(
        "--admin-password", default=os.getenv("ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
    )
    parser.add_argument(
        "--ws-clients",
        type=int,
        default=int(os.getenv("LOADTEST_WS_CLIENTS", DEFAULT_WS_CLIENTS)),
    )
    parser.add_argument(
        "--orders",
        type=int,
        default=int(os.getenv("LOADTEST_ORDERS", DEFAULT_ORDER_COUNT)),
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=int(os.getenv("LOADTEST_CONCURRENCY", DEFAULT_CONCURRENCY)),
    )
    parser.add_argument(
        "--order-delay-ms",
        type=int,
        default=int(os.getenv("LOADTEST_ORDER_DELAY_MS", "0")),
    )
    parser.add_argument(
        "--item-count",
        type=int,
        default=int(os.getenv("LOADTEST_ITEM_COUNT", "1")),
    )
    parser.add_argument(
        "--item-price",
        default=os.getenv("LOADTEST_ITEM_PRICE", "199.00"),
    )
    parser.add_argument(
        "--item-name",
        default=os.getenv("LOADTEST_ITEM_NAME", "Load Test Roll"),
    )
    parser.add_argument(
        "--source-channel",
        default=os.getenv("LOADTEST_SOURCE_CHANNEL", SourceChannel.POS.value),
    )
    parser.add_argument(
        "--payment-type",
        default=os.getenv("LOADTEST_PAYMENT_TYPE", ""),
        help="Explicit payment type (cash/card/online). Empty means auto-detect.",
    )
    parser.add_argument(
        "--no-auto-detect-payment-type",
        action="store_true",
        default=os.getenv("LOADTEST_NO_AUTO_DETECT_PAYMENT_TYPE", "0") == "1",
    )
    parser.add_argument(
        "--report-path",
        default=os.getenv("LOADTEST_REPORT_PATH", ""),
        help="Optional markdown report path to print in human-readable form.",
    )
    args = parser.parse_args()

    return LoadTestConfig(
        api_base_url=args.api_base_url.rstrip("/"),
        admin_email=args.admin_email,
        admin_password=args.admin_password,
        ws_clients=max(1, args.ws_clients),
        order_count=max(1, args.orders),
        concurrency=max(1, args.concurrency),
        order_delay_ms=max(0, args.order_delay_ms),
        item_count=max(1, args.item_count),
        item_price=Decimal(str(args.item_price)),
        item_name=args.item_name,
        source_channel=SourceChannel(args.source_channel),
        payment_type=PaymentType(args.payment_type) if args.payment_type else None,
        auto_detect_payment_type=not args.no_auto_detect_payment_type,
        report_path=Path(args.report_path).expanduser() if args.report_path else None,
    )


def _parse_ws_base_url(api_base_url: str) -> str:
    parsed = urlparse(api_base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunparse((scheme, parsed.netloc, parsed.path, "", "", ""))


def _approx_p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    try:
        return statistics.quantiles(ordered, n=20, method="inclusive")[18]
    except Exception:
        idx = max(0, min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1)))))
        return ordered[idx]


def _ms(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


async def login(client: httpx.AsyncClient, config: LoadTestConfig) -> dict[str, Any]:
    response = await client.post(
        "/auth/login",
        json={"email": config.admin_email, "password": config.admin_password},
    )
    response.raise_for_status()
    payload = response.json()
    if "access_token" not in payload:
        raise RuntimeError(f"Login response missing access_token: {payload}")
    return payload


async def choose_point(client: httpx.AsyncClient) -> dict[str, Any]:
    response = await client.get("/points")
    response.raise_for_status()
    points = response.json()
    if not points:
        raise RuntimeError("No accessible points returned by GET /points")
    for point in points:
        if point.get("is_active", False):
            return point
    return points[0]


async def detect_payment_type(
    client: httpx.AsyncClient,
    point_id: str,
    source_channel: SourceChannel,
) -> tuple[PaymentType, str | None]:
    for payment_type in DEFAULT_PAYMENT_TYPES:
        payload = OrderCreate(
            point_id=uuid.UUID(point_id),
            payment_type=payment_type,
            source_channel=source_channel,
            items=[
                OrderItem(
                    name="Load Test Probe",
                    quantity=1,
                    price=Decimal("1.00"),
                )
            ],
            notes="loadtest probe",
        ).model_dump(mode="json")
        response = await client.post("/orders", json=payload)
        if response.status_code == 201:
            body = response.json()
            return payment_type, body.get("id")
        if response.status_code != 422:
            response.raise_for_status()
    raise RuntimeError(
        "Unable to create a probe order with cash/card/online; "
        "set LOADTEST_PAYMENT_TYPE explicitly."
    )


async def ws_consumer(
    client_id: int,
    ws_url: str,
    token: str,
    point_id: str,
    order_created_at: dict[str, float],
    pending_receipts: dict[str, list[tuple[int, float]]],
    events: list[WsEvent],
    lock: asyncio.Lock,
    ready: asyncio.Event,
    stop: asyncio.Event,
) -> None:
    uri = f"{ws_url}/ws/orders/{point_id}?token={token}"
    try:
        async with websockets.connect(uri, ping_interval=None) as ws:
            message = await asyncio.wait_for(ws.recv(), timeout=10)
            if isinstance(message, bytes):
                message = message.decode()
            connected = json.loads(message)
            if connected.get("type") != "connected":
                raise RuntimeError(f"Unexpected WS handshake payload: {connected}")
            ready.set()
            while not stop.is_set():
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                if isinstance(message, bytes):
                    message = message.decode()
                payload = json.loads(message)
                if payload.get("type") != "order_created":
                    continue
                order_id = str(payload.get("order_id", ""))
                received_at = time.perf_counter()
                async with lock:
                    created_at = order_created_at.get(order_id)
                    if created_at is None:
                        pending_receipts.setdefault(order_id, []).append((client_id, received_at))
                        continue
                    events.append(
                        WsEvent(
                            client_id=client_id,
                            order_id=order_id,
                            received_at=received_at,
                            latency_ms=(received_at - created_at) * 1000.0,
                        )
                    )
    except Exception as exc:
        raise RuntimeError(f"WS client {client_id} failed: {exc}") from exc


async def create_order(
    client: httpx.AsyncClient,
    config: LoadTestConfig,
    point_id: str,
    payment_type: PaymentType,
    index: int,
) -> OrderAttempt:
    payload = OrderCreate(
        point_id=uuid.UUID(point_id),
        payment_type=payment_type,
        source_channel=config.source_channel,
        items=[
            OrderItem(
                name=config.item_name,
                quantity=config.item_count,
                price=config.item_price,
            )
        ],
        notes=f"loadtest order #{index}",
    ).model_dump(mode="json")
    if config.order_delay_ms:
        await asyncio.sleep((index - 1) * config.order_delay_ms / 1000.0)
    start = time.perf_counter()
    try:
        response = await client.post("/orders", json=payload)
        latency_ms = (time.perf_counter() - start) * 1000.0
        if response.status_code != 201:
            return OrderAttempt(
                index=index,
                order_id=None,
                ok=False,
                status_code=response.status_code,
                started_at=start,
                latency_ms=latency_ms,
                error=response.text,
            )
        body = response.json()
        return OrderAttempt(
            index=index,
            order_id=str(body.get("id")),
            ok=True,
            status_code=response.status_code,
            started_at=start,
            latency_ms=latency_ms,
        )
    except Exception as exc:
        return OrderAttempt(
            index=index,
            order_id=None,
            ok=False,
            status_code=None,
            started_at=start,
            latency_ms=(time.perf_counter() - start) * 1000.0,
            error=str(exc),
        )


def render_report(summary: RunSummary) -> str:
    api_latencies = summary.api_latencies_ms
    ws_latencies = summary.ws_latencies_ms
    lines = [
        "# TASK-046 Load Test Report",
        "",
        f"- Run timestamp: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        f"- API base URL: `{summary.config.api_base_url}`",
        f"- Point: `{summary.point_name}` (`{summary.point_id}`)",
        f"- Admin: `{summary.admin_user.get('email', 'n/a')}`",
        f"- WS clients: `{summary.config.ws_clients}`",
        f"- Orders attempted: `{summary.config.order_count}`",
        f"- Orders succeeded: `{summary.successful_requests}`",
        f"- Orders failed: `{summary.failed_requests}`",
        f"- Runtime: `{summary.runtime_s:.2f}s`",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Successful requests | {summary.successful_requests} |",
        f"| Failed requests | {summary.failed_requests} |",
        f"| API avg latency (ms) | {_ms(sum(api_latencies) / len(api_latencies) if api_latencies else None)} |",
        f"| API max latency (ms) | {_ms(max(api_latencies) if api_latencies else None)} |",
        f"| API approx p95 latency (ms) | {_ms(_approx_p95(api_latencies))} |",
        f"| WS delivered events | {len(ws_latencies)} |",
        f"| WS expected events | {summary.expected_ws_events} |",
        f"| WS avg delivery delay (ms) | {_ms(sum(ws_latencies) / len(ws_latencies) if ws_latencies else None)} |",
        f"| WS max delivery delay (ms) | {_ms(max(ws_latencies) if ws_latencies else None)} |",
        f"| WS approx p95 delivery delay (ms) | {_ms(_approx_p95(ws_latencies))} |",
        "",
        "## Observations",
        "",
        "- If WS delivered events are lower than expected, the likely bottleneck is broadcast timing or client readiness.",
        "- If API p95 diverges sharply from average, inspect DB commit time and background task contention.",
        "- If latencies grow with concurrency, the current hot path is likely synchronous DB work plus post-commit fan-out.",
        "",
        "## Notes",
        "",
        f"- Payment type used: `{summary.payment_type}`",
    ]
    if summary.probe_order_id:
        lines.append(f"- Probe order id: `{summary.probe_order_id}`")
    if summary.probe_payment_type:
        lines.append(f"- Probe payment type: `{summary.probe_payment_type}`")
    lines.extend(
        [
            "",
            "## Raw Order Results",
            "",
            "| # | Status | Latency ms | Order ID | Error |",
            "| --- | --- | ---: | --- | --- |",
        ]
    )
    for attempt in summary.order_attempts:
        lines.append(
            f"| {attempt.index} | {'ok' if attempt.ok else 'fail'} | "
            f"{_ms(attempt.latency_ms)} | {attempt.order_id or '-'} | "
            f"{(attempt.error or '').replace('|', '\\|')[:120]} |"
        )
    return "\n".join(lines) + "\n"


async def main() -> None:
    config = parse_args()
    ws_base_url = _parse_ws_base_url(config.api_base_url)
    timeout = httpx.Timeout(20.0, connect=10.0)
    limits = httpx.Limits(max_connections=max(10, config.concurrency * 2), max_keepalive_connections=10)
    run_started = time.perf_counter()
    order_created_at: dict[str, float] = {}
    pending_receipts: dict[str, list[tuple[int, float]]] = {}
    ws_events: list[WsEvent] = []
    state_lock = asyncio.Lock()
    ws_ready_events: list[asyncio.Event] = [asyncio.Event() for _ in range(config.ws_clients)]
    ws_stop = asyncio.Event()
    ws_tasks: list[asyncio.Task[None]] = []

    async with httpx.AsyncClient(base_url=config.api_base_url, timeout=timeout, limits=limits) as client:
        login_data = await login(client, config)
        token = login_data["access_token"]
        admin_user = login_data["user"]
        client.headers.update({"Authorization": f"Bearer {token}"})

        point = await choose_point(client)
        point_id = str(point["id"])
        point_name = str(point["name"])

        payment_type = config.payment_type
        probe_order_id = None
        probe_payment_type = None
        if payment_type is None and config.auto_detect_payment_type:
            payment_type, probe_order_id = await detect_payment_type(client, point_id, config.source_channel)
            probe_payment_type = payment_type.value

        if payment_type is None:
            payment_type = PaymentType.CASH

        for idx in range(config.ws_clients):
            ws_tasks.append(
                asyncio.create_task(
                    ws_consumer(
                        client_id=idx + 1,
                        ws_url=ws_base_url,
                        token=token,
                        point_id=point_id,
                        order_created_at=order_created_at,
                        pending_receipts=pending_receipts,
                        events=ws_events,
                        lock=state_lock,
                        ready=ws_ready_events[idx],
                        stop=ws_stop,
                    )
                )
            )

        await asyncio.wait_for(
            asyncio.gather(*(event.wait() for event in ws_ready_events)),
            timeout=15.0,
        )
        await asyncio.sleep(0.25)

        sem = asyncio.Semaphore(config.concurrency)

        async def _bounded_create(index: int) -> OrderAttempt:
            async with sem:
                attempt = await create_order(client, config, point_id, payment_type, index)
                if attempt.ok and attempt.order_id:
                    async with state_lock:
                        created_at = attempt.started_at or time.perf_counter()
                        order_created_at[attempt.order_id] = created_at
                        buffered = pending_receipts.pop(attempt.order_id, [])
                        for client_id, received_at in buffered:
                            ws_events.append(
                                WsEvent(
                                    client_id=client_id,
                                    order_id=attempt.order_id,
                                    received_at=received_at,
                                    latency_ms=(received_at - created_at) * 1000.0,
                                )
                            )
                return attempt

        order_tasks = [asyncio.create_task(_bounded_create(idx + 1)) for idx in range(config.order_count)]
        order_attempts: list[OrderAttempt] = []
        try:
            for coro in asyncio.as_completed(order_tasks):
                attempt = await coro
                order_attempts.append(attempt)
        finally:
            ws_stop.set()
            ws_results = await asyncio.gather(*ws_tasks, return_exceptions=True)
            errors = [result for result in ws_results if isinstance(result, Exception)]
            if errors:
                raise RuntimeError("; ".join(str(err) for err in errors))

    runtime_s = time.perf_counter() - run_started
    summary = RunSummary(
        config=config,
        admin_user=admin_user,
        point_id=point_id,
        point_name=point_name,
        payment_type=payment_type.value,
        order_attempts=sorted(order_attempts, key=lambda item: item.index),
        ws_events=ws_events,
        ws_connected=config.ws_clients,
        runtime_s=runtime_s,
        probe_order_id=probe_order_id,
        probe_payment_type=probe_payment_type,
    )

    print(render_report(summary))
    print(
        json.dumps(
            {
                "successful_requests": summary.successful_requests,
                "failed_requests": summary.failed_requests,
                "api_avg_latency_ms": (
                    sum(summary.api_latencies_ms) / len(summary.api_latencies_ms)
                    if summary.api_latencies_ms
                    else None
                ),
                "api_max_latency_ms": max(summary.api_latencies_ms) if summary.api_latencies_ms else None,
                "api_p95_latency_ms": _approx_p95(summary.api_latencies_ms),
                "ws_delivered_events": len(summary.ws_latencies_ms),
                "ws_expected_events": summary.expected_ws_events,
                "ws_avg_delivery_delay_ms": (
                    sum(summary.ws_latencies_ms) / len(summary.ws_latencies_ms)
                    if summary.ws_latencies_ms
                    else None
                ),
                "ws_max_delivery_delay_ms": max(summary.ws_latencies_ms) if summary.ws_latencies_ms else None,
                "ws_p95_delivery_delay_ms": _approx_p95(summary.ws_latencies_ms),
            },
            indent=2,
            sort_keys=True,
        )
    )

    if config.report_path:
        config.report_path.parent.mkdir(parents=True, exist_ok=True)
        config.report_path.write_text(render_report(summary), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
