from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.ai import build_ai_provider
from backend.app.models.dish import Dish
from backend.app.models.dish_ingredient import DishIngredient
from backend.app.models.ingredient import Ingredient
from backend.app.models.order import Order, OrderStatus
from backend.app.models.point import Point
from backend.app.models.stock_item import StockItem
from backend.app.models.stock_movement import MovementType, StockMovement
from backend.app.models.user import User, UserRole
from backend.app.modules.analytics.schemas import (
    AnalyticsModuleStatus,
    AnalyticsSummaryResponse,
    AnomaliesResponse,
    AnomalySignal,
    AssistantChatResponse,
    AssistantEvidenceItem,
    ChannelAnalyticsItem,
    DishAnalyticsItem,
    DishesAnalyticsResponse,
    ForecastItem,
    ProcurementForecastResponse,
    RevenuePointItem,
)
from backend.app.modules.franchisee.service import (
    get_accessible_point_ids_for_user,
    get_accessible_points_for_user,
)

TWO_PLACES = Decimal("0.01")
THREE_PLACES = Decimal("0.001")


@dataclass(slots=True)
class AnalyticsScope:
    points: list[Point]
    context_scope: str


def get_status() -> AnalyticsModuleStatus:
    return AnalyticsModuleStatus(module="analytics", status="active")


def _ensure_supported_period(period: str) -> str:
    normalized = period.strip().lower()
    if normalized not in {"day", "week", "month"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="period must be one of: day, week, month",
        )
    return normalized


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _period_start(period: str, now: datetime | None = None) -> datetime:
    moment = now or _now_utc()
    normalized = _ensure_supported_period(period)
    if normalized == "day":
        return datetime.combine(moment.date(), time.min, tzinfo=UTC)
    if normalized == "week":
        return datetime.combine(
            moment.date() - timedelta(days=moment.weekday()),
            time.min,
            tzinfo=UTC,
        )
    return datetime(moment.year, moment.month, 1, tzinfo=UTC)


def _day_start(days_ago: int = 0) -> datetime:
    return datetime.combine(
        (_now_utc() - timedelta(days=days_ago)).date(),
        time.min,
        tzinfo=UTC,
    )


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _quantize(value: Decimal, template: Decimal = TWO_PLACES) -> Decimal:
    return value.quantize(template, rounding=ROUND_HALF_UP)


def _money_text(value: Decimal) -> str:
    return f"{_quantize(value)} ₽"


def _quantity_text(value: Decimal) -> str:
    return f"{_quantize(value, THREE_PLACES)}"


async def _get_accessible_points(user: User, db: AsyncSession) -> list[Point]:
    return await get_accessible_points_for_user(db, user)


async def _require_accessible_point(
    point_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> Point:
    result = await db.execute(select(Point).where(Point.id == point_id))
    point = result.scalar_one_or_none()
    if point is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Point not found")

    accessible_point_ids = await get_accessible_point_ids_for_user(db, user)
    if point_id not in accessible_point_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return point


async def _resolve_scope(
    *,
    point_id: uuid.UUID | None,
    user: User,
    db: AsyncSession,
) -> AnalyticsScope:
    if point_id is not None:
        point = await _require_accessible_point(point_id, user, db)
        return AnalyticsScope(points=[point], context_scope=point.name)

    points = await _get_accessible_points(user, db)
    if user.role == UserRole.SUPER_ADMIN:
        return AnalyticsScope(points=points, context_scope="Вся сеть")
    if not points:
        return AnalyticsScope(points=[], context_scope="Назначенные точки")
    if len(points) == 1:
        return AnalyticsScope(points=points, context_scope=points[0].name)
    return AnalyticsScope(points=points, context_scope=f"{len(points)} точек")


async def _load_orders(
    *,
    point_ids: list[uuid.UUID],
    db: AsyncSession,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    exclude_cancelled: bool = True,
) -> list[Order]:
    if not point_ids:
        return []

    query = select(Order).where(Order.point_id.in_(point_ids))
    if exclude_cancelled:
        query = query.where(Order.status != OrderStatus.CANCELLED)
    if start_at is not None:
        query = query.where(Order.created_at >= start_at)
    if end_at is not None:
        query = query.where(Order.created_at < end_at)
    query = query.order_by(Order.created_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_revenue(
    *,
    period: str,
    point_id: uuid.UUID | None,
    user: User,
    db: AsyncSession,
) -> list[RevenuePointItem]:
    scope = await _resolve_scope(point_id=point_id, user=user, db=db)
    point_ids = [point.id for point in scope.points]
    if not point_ids:
        return []

    start_at = _period_start(period)
    result = await db.execute(
        select(
            Order.point_id,
            func.coalesce(func.sum(Order.total_amount), Decimal("0")),
            func.count(Order.id),
        )
        .where(
            Order.point_id.in_(point_ids),
            Order.status != OrderStatus.CANCELLED,
            Order.created_at >= start_at,
        )
        .group_by(Order.point_id)
    )
    aggregates = {
        row[0]: (
            _to_decimal(row[1]),
            int(row[2]),
        )
        for row in result.all()
    }

    items = []
    for point in scope.points:
        total_revenue, order_count = aggregates.get(point.id, (Decimal("0"), 0))
        items.append(
            RevenuePointItem(
                point_id=point.id,
                point_name=point.name,
                total_revenue=_quantize(total_revenue),
                order_count=order_count,
            )
        )
    items.sort(key=lambda item: (item.total_revenue, item.order_count), reverse=True)
    return items


async def get_dishes_analytics(
    *,
    period: str,
    point_id: uuid.UUID | None,
    limit: int,
    user: User,
    db: AsyncSession,
) -> DishesAnalyticsResponse:
    scope = await _resolve_scope(point_id=point_id, user=user, db=db)
    limit = max(1, min(limit, 50))
    orders = await _load_orders(
        point_ids=[point.id for point in scope.points],
        db=db,
        start_at=_period_start(period),
    )

    aggregates: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {"quantity": Decimal("0"), "revenue": Decimal("0")}
    )
    for order in orders:
        for raw_item in order.items or []:
            name = str(raw_item.get("name") or "Unknown")
            quantity = _to_decimal(raw_item.get("quantity"))
            price = _to_decimal(raw_item.get("price"))
            aggregates[name]["quantity"] += quantity
            aggregates[name]["revenue"] += quantity * price

    def to_item(name: str, values: dict[str, Decimal]) -> DishAnalyticsItem:
        return DishAnalyticsItem(
            dish_name=name,
            total_quantity=_quantize(values["quantity"], THREE_PLACES),
            total_revenue=_quantize(values["revenue"]),
        )

    ranked = [to_item(name, values) for name, values in aggregates.items()]
    ranked.sort(
        key=lambda item: (item.total_quantity, item.total_revenue, item.dish_name),
        reverse=True,
    )
    bottom = sorted(
        ranked,
        key=lambda item: (item.total_quantity, item.total_revenue, item.dish_name),
    )
    return DishesAnalyticsResponse(top=ranked[:limit], bottom=bottom[:limit])


async def get_channels_analytics(
    *,
    period: str,
    point_id: uuid.UUID | None,
    user: User,
    db: AsyncSession,
) -> list[ChannelAnalyticsItem]:
    scope = await _resolve_scope(point_id=point_id, user=user, db=db)
    point_ids = [point.id for point in scope.points]
    if not point_ids:
        return []

    result = await db.execute(
        select(
            Order.source_channel,
            func.count(Order.id),
            func.coalesce(func.sum(Order.total_amount), Decimal("0")),
        )
        .where(
            Order.point_id.in_(point_ids),
            Order.status != OrderStatus.CANCELLED,
            Order.created_at >= _period_start(period),
        )
        .group_by(Order.source_channel)
    )
    items = [
        ChannelAnalyticsItem(
            source_channel=row[0].value if hasattr(row[0], "value") else str(row[0]),
            order_count=int(row[1]),
            total_revenue=_quantize(_to_decimal(row[2])),
        )
        for row in result.all()
    ]
    items.sort(key=lambda item: (item.total_revenue, item.order_count), reverse=True)
    return items


async def get_summary(
    *,
    point_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> AnalyticsSummaryResponse:
    await _require_accessible_point(point_id, user, db)

    today_start = _day_start(0)
    tomorrow_start = today_start + timedelta(days=1)

    orders_today = await _load_orders(
        point_ids=[point_id],
        db=db,
        start_at=today_start,
        end_at=tomorrow_start,
    )
    total_orders_today = len(orders_today)
    total_revenue_today = sum(
        (_to_decimal(order.total_amount) for order in orders_today),
        start=Decimal("0"),
    )

    pending_result = await db.execute(
        select(func.count(Order.id)).where(
            Order.point_id == point_id,
            Order.status.in_(
                [OrderStatus.NEW, OrderStatus.IN_PROGRESS, OrderStatus.READY]
            ),
        )
    )
    pending_orders = int(pending_result.scalar() or 0)

    dish_quantities: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for order in orders_today:
        for raw_item in order.items or []:
            name = str(raw_item.get("name") or "Unknown")
            dish_quantities[name] += _to_decimal(raw_item.get("quantity"))

    top_dish_today = None
    if dish_quantities:
        top_dish_today = max(
            dish_quantities.items(),
            key=lambda item: (item[1], item[0]),
        )[0]

    return AnalyticsSummaryResponse(
        total_orders_today=total_orders_today,
        total_revenue_today=_quantize(total_revenue_today),
        pending_orders=pending_orders,
        top_dish_today=top_dish_today,
    )


async def _load_recipe_snapshot(
    *,
    orders: list[Order],
    db: AsyncSession,
) -> tuple[
    dict[uuid.UUID, Dish],
    dict[str, Dish],
    dict[uuid.UUID, list[tuple[Ingredient, Decimal]]],
]:
    dish_ids: set[uuid.UUID] = set()
    dish_names: set[str] = set()
    for order in orders:
        for raw_item in order.items or []:
            raw_dish_id = raw_item.get("dish_id")
            if raw_dish_id:
                try:
                    dish_ids.add(uuid.UUID(str(raw_dish_id)))
                except ValueError:
                    pass
            if raw_item.get("name"):
                dish_names.add(str(raw_item["name"]))

    if not dish_ids and not dish_names:
        return {}, {}, {}

    filters = []
    if dish_ids:
        filters.append(Dish.id.in_(dish_ids))
    if dish_names:
        filters.append(Dish.name.in_(dish_names))

    dish_result = await db.execute(
        select(Dish).where(or_(*filters), Dish.is_active.is_(True))
    )
    dishes = list(dish_result.scalars().all())
    dishes_by_id = {dish.id: dish for dish in dishes}
    dishes_by_name = {dish.name: dish for dish in dishes}
    if not dishes_by_id:
        return dishes_by_id, dishes_by_name, {}

    recipe_result = await db.execute(
        select(DishIngredient, Ingredient)
        .join(Ingredient, DishIngredient.ingredient_id == Ingredient.id)
        .where(DishIngredient.dish_id.in_(list(dishes_by_id.keys())))
    )
    recipes: dict[uuid.UUID, list[tuple[Ingredient, Decimal]]] = defaultdict(list)
    for dish_ingredient, ingredient in recipe_result.all():
        recipes[dish_ingredient.dish_id].append(
            (ingredient, _to_decimal(dish_ingredient.quantity_per_portion))
        )
    return dishes_by_id, dishes_by_name, recipes


async def get_procurement_forecast(
    *,
    point_id: uuid.UUID,
    horizon_days: int,
    lookback_days: int,
    user: User,
    db: AsyncSession,
) -> ProcurementForecastResponse:
    if horizon_days <= 0 or lookback_days <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="horizon_days and lookback_days must be positive",
        )

    point = await _require_accessible_point(point_id, user, db)

    orders = await _load_orders(
        point_ids=[point_id],
        db=db,
        start_at=_now_utc() - timedelta(days=lookback_days),
    )
    dishes_by_id, dishes_by_name, recipes = await _load_recipe_snapshot(orders=orders, db=db)

    ingredient_usage: dict[uuid.UUID, Decimal] = defaultdict(lambda: Decimal("0"))
    ingredient_meta: dict[uuid.UUID, Ingredient] = {}

    for order in orders:
        for raw_item in order.items or []:
            dish: Dish | None = None
            raw_dish_id = raw_item.get("dish_id")
            if raw_dish_id:
                try:
                    dish = dishes_by_id.get(uuid.UUID(str(raw_dish_id)))
                except ValueError:
                    dish = None
            if dish is None and raw_item.get("name"):
                dish = dishes_by_name.get(str(raw_item["name"]))
            if dish is None:
                continue

            portions = _to_decimal(raw_item.get("quantity"))
            for ingredient, quantity_per_portion in recipes.get(dish.id, []):
                ingredient_usage[ingredient.id] += quantity_per_portion * portions
                ingredient_meta[ingredient.id] = ingredient

    stock_result = await db.execute(
        select(StockItem, Ingredient)
        .join(Ingredient, StockItem.ingredient_id == Ingredient.id)
        .where(StockItem.point_id == point_id)
    )
    stock_map: dict[uuid.UUID, Decimal] = {}
    for stock_item, ingredient in stock_result.all():
        stock_map[ingredient.id] = _to_decimal(stock_item.quantity)
        ingredient_meta[ingredient.id] = ingredient

    items: list[ForecastItem] = []
    ingredient_ids = set(stock_map) | set(ingredient_usage)
    for ingredient_id in ingredient_ids:
        ingredient = ingredient_meta[ingredient_id]
        current_stock = stock_map.get(ingredient_id, Decimal("0"))
        total_usage = ingredient_usage.get(ingredient_id, Decimal("0"))
        avg_daily_usage = total_usage / Decimal(str(lookback_days))
        forecast_demand = avg_daily_usage * Decimal(str(horizon_days))
        recommended_purchase = max(
            Decimal("0"),
            forecast_demand + _to_decimal(ingredient.min_stock_level) - current_stock,
        )
        if forecast_demand <= 0 and current_stock >= _to_decimal(ingredient.min_stock_level):
            continue

        items.append(
            ForecastItem(
                ingredient_id=ingredient.id,
                ingredient_name=ingredient.name,
                unit=ingredient.unit,
                current_stock=_quantize(current_stock, THREE_PLACES),
                min_stock_level=_quantize(
                    _to_decimal(ingredient.min_stock_level),
                    THREE_PLACES,
                ),
                avg_daily_usage=_quantize(avg_daily_usage, THREE_PLACES),
                forecast_demand=_quantize(forecast_demand, THREE_PLACES),
                recommended_purchase=_quantize(recommended_purchase, THREE_PLACES),
            )
        )

    items.sort(
        key=lambda item: (
            item.recommended_purchase,
            item.forecast_demand,
            item.ingredient_name,
        ),
        reverse=True,
    )
    return ProcurementForecastResponse(
        point_id=point.id,
        point_name=point.name,
        horizon_days=horizon_days,
        lookback_days=lookback_days,
        generated_at=_now_utc(),
        items=items,
    )


async def _revenue_by_point_for_window(
    *,
    point_ids: list[uuid.UUID],
    start_at: datetime,
    end_at: datetime,
    db: AsyncSession,
) -> dict[uuid.UUID, Decimal]:
    if not point_ids:
        return {}

    result = await db.execute(
        select(
            Order.point_id,
            func.coalesce(func.sum(Order.total_amount), Decimal("0")),
        )
        .where(
            Order.point_id.in_(point_ids),
            Order.status != OrderStatus.CANCELLED,
            Order.created_at >= start_at,
            Order.created_at < end_at,
        )
        .group_by(Order.point_id)
    )
    return {row[0]: _to_decimal(row[1]) for row in result.all()}


async def _manual_writeoffs_by_point_for_window(
    *,
    point_ids: list[uuid.UUID],
    start_at: datetime,
    end_at: datetime,
    db: AsyncSession,
) -> dict[uuid.UUID, Decimal]:
    if not point_ids:
        return {}

    result = await db.execute(
        select(
            StockItem.point_id,
            StockMovement.movement_type,
            StockMovement.quantity,
            StockMovement.reason,
        )
        .join(StockItem, StockMovement.stock_item_id == StockItem.id)
        .where(
            StockItem.point_id.in_(point_ids),
            StockMovement.created_at >= start_at,
            StockMovement.created_at < end_at,
        )
    )
    totals: dict[uuid.UUID, Decimal] = defaultdict(lambda: Decimal("0"))
    for point_ref, movement_type, quantity, reason in result.all():
        movement = movement_type.value if hasattr(movement_type, "value") else str(movement_type)
        reason_text = reason or ""
        if movement == MovementType.OUT.value and reason_text.startswith("order:"):
            continue
        if movement not in {MovementType.OUT.value, MovementType.ADJUSTMENT.value}:
            continue
        totals[point_ref] += _to_decimal(quantity)
    return totals


async def get_anomalies(
    *,
    point_id: uuid.UUID | None,
    limit: int,
    user: User,
    db: AsyncSession,
) -> AnomaliesResponse:
    scope = await _resolve_scope(point_id=point_id, user=user, db=db)
    points = scope.points
    point_ids = [point.id for point in points]
    if not point_ids:
        return AnomaliesResponse(generated_at=_now_utc(), signals=[])

    now = _now_utc()
    current_start = now - timedelta(days=7)
    current_end = now
    previous_start = now - timedelta(days=14)
    previous_end = now - timedelta(days=7)
    baseline_writeoff_start = now - timedelta(days=28)

    revenue_now = await _revenue_by_point_for_window(
        point_ids=point_ids,
        start_at=current_start,
        end_at=current_end,
        db=db,
    )
    revenue_prev = await _revenue_by_point_for_window(
        point_ids=point_ids,
        start_at=previous_start,
        end_at=previous_end,
        db=db,
    )
    writeoffs_now = await _manual_writeoffs_by_point_for_window(
        point_ids=point_ids,
        start_at=current_start,
        end_at=current_end,
        db=db,
    )
    writeoffs_baseline = await _manual_writeoffs_by_point_for_window(
        point_ids=point_ids,
        start_at=baseline_writeoff_start,
        end_at=previous_end,
        db=db,
    )

    signals: list[AnomalySignal] = []
    point_name_map = {point.id: point.name for point in points}
    for point_ref in point_ids:
        current_revenue = revenue_now.get(point_ref, Decimal("0"))
        previous_revenue = revenue_prev.get(point_ref, Decimal("0"))
        if previous_revenue > 0 and current_revenue <= previous_revenue * Decimal("0.6"):
            severity = "high" if current_revenue <= previous_revenue * Decimal("0.4") else "medium"
            change_ratio = Decimal("0")
            if previous_revenue > 0:
                change_ratio = (current_revenue / previous_revenue) * Decimal("100")
            signals.append(
                AnomalySignal(
                    type="sales_drop",
                    severity=severity,
                    title="Падение выручки",
                    description=(
                        f"За последние 7 дней выручка упала до "
                        f"{change_ratio.quantize(TWO_PLACES)}% от предыдущей недели."
                    ),
                    metric="weekly_revenue",
                    current_value=_money_text(current_revenue),
                    baseline_value=_money_text(previous_revenue),
                    point_id=point_ref,
                    point_name=point_name_map.get(point_ref),
                )
            )

        current_writeoff = writeoffs_now.get(point_ref, Decimal("0"))
        baseline_total = writeoffs_baseline.get(point_ref, Decimal("0"))
        baseline_normalized = baseline_total / Decimal("3") if baseline_total > 0 else Decimal("0")
        if current_writeoff > 0 and (
            (baseline_normalized > 0 and current_writeoff >= baseline_normalized * Decimal("2"))
            or current_writeoff >= Decimal("15")
        ):
            severity = "high" if current_writeoff >= max(
                baseline_normalized * Decimal("3"),
                Decimal("25"),
            ) else "medium"
            signals.append(
                AnomalySignal(
                    type="suspicious_writeoff",
                    severity=severity,
                    title="Подозрительные списания",
                    description=(
                        "Ручные списания или корректировки за 7 дней заметно выше обычного уровня."
                    ),
                    metric="manual_writeoff_qty",
                    current_value=_quantity_text(current_writeoff),
                    baseline_value=_quantity_text(baseline_normalized),
                    point_id=point_ref,
                    point_name=point_name_map.get(point_ref),
                )
            )

    severity_order = {"high": 0, "medium": 1, "low": 2}
    signals.sort(
        key=lambda item: (
            severity_order.get(item.severity, 99),
            item.point_name or "",
            item.title,
        )
    )
    return AnomaliesResponse(generated_at=_now_utc(), signals=signals[: max(1, min(limit, 50))])


def _build_assistant_evidence(
    *,
    revenue: list[RevenuePointItem],
    channels: list[ChannelAnalyticsItem],
    dishes: DishesAnalyticsResponse,
    anomalies: AnomaliesResponse,
    forecast: ProcurementForecastResponse | None,
) -> list[AssistantEvidenceItem]:
    total_revenue = sum((item.total_revenue for item in revenue), start=Decimal("0"))
    total_orders = sum((item.order_count for item in revenue), start=0)
    evidence = [
        AssistantEvidenceItem(
            label="Выручка за неделю",
            value=_money_text(total_revenue),
            detail=f"Заказов: {total_orders}",
        )
    ]

    if channels:
        top_channel = channels[0]
        evidence.append(
            AssistantEvidenceItem(
                label="Главный канал",
                value=top_channel.source_channel,
                detail=(
                    f"{top_channel.order_count} заказов, "
                    f"{_money_text(top_channel.total_revenue)}"
                ),
            )
        )

    if dishes.top:
        top_dish = dishes.top[0]
        evidence.append(
            AssistantEvidenceItem(
                label="Лидер по блюдам",
                value=top_dish.dish_name,
                detail=(
                    f"{_quantity_text(top_dish.total_quantity)} порций, "
                    f"{_money_text(top_dish.total_revenue)}"
                ),
            )
        )
    if dishes.bottom:
        weak_dish = dishes.bottom[0]
        evidence.append(
            AssistantEvidenceItem(
                label="Слабое блюдо",
                value=weak_dish.dish_name,
                detail=(
                    f"{_quantity_text(weak_dish.total_quantity)} порций, "
                    f"{_money_text(weak_dish.total_revenue)}"
                ),
            )
        )

    if anomalies.signals:
        top_signal = anomalies.signals[0]
        evidence.append(
            AssistantEvidenceItem(
                label="Критичный сигнал",
                value=top_signal.title,
                detail=(
                    f"{top_signal.point_name or 'Сеть'}: "
                    f"{top_signal.current_value} vs {top_signal.baseline_value or 'n/a'}"
                ),
            )
        )

    if forecast is not None and forecast.items:
        hottest_item = forecast.items[0]
        evidence.append(
            AssistantEvidenceItem(
                label="Закупка недели",
                value=hottest_item.ingredient_name,
                detail=(
                    f"Докупить {hottest_item.recommended_purchase} {hottest_item.unit}, "
                    f"остаток {hottest_item.current_stock} {hottest_item.unit}"
                ),
            )
        )
    return evidence


def _build_assistant_suggestions(
    *,
    anomalies: AnomaliesResponse,
    forecast: ProcurementForecastResponse | None,
    dishes: DishesAnalyticsResponse,
) -> list[str]:
    suggestions: list[str] = []
    if anomalies.signals:
        first = anomalies.signals[0]
        suggestions.append(
            f"Проверьте сигнал '{first.title}' по точке {first.point_name or 'сети'}."
        )
    if forecast is not None:
        risky = [item for item in forecast.items if item.recommended_purchase > 0]
        if risky:
            item = risky[0]
            suggestions.append(
                f"Запланируйте закупку {item.ingredient_name}: "
                f"{item.recommended_purchase} {item.unit}."
            )
    if dishes.bottom:
        item = dishes.bottom[0]
        suggestions.append(
            f"Пересмотрите спрос на {item.dish_name}: "
            f"всего {_quantity_text(item.total_quantity)} порций."
        )
    return suggestions[:3]


def _build_fallback_answer(
    *,
    context_scope: str,
    evidence: list[AssistantEvidenceItem],
    anomalies: AnomaliesResponse,
    suggestions: list[str],
) -> str:
    parts = [f"Контекст: {context_scope}."]
    for item in evidence:
        detail = f" ({item.detail})" if item.detail else ""
        parts.append(f"{item.label}: {item.value}{detail}.")
    if anomalies.signals:
        parts.append(f"Найдено сигналов: {len(anomalies.signals)}.")
    if suggestions:
        parts.append("Приоритетные действия: " + " ".join(suggestions))
    return " ".join(parts)


async def answer_assistant_question(
    *,
    question: str,
    point_id: uuid.UUID | None,
    user: User,
    db: AsyncSession,
) -> AssistantChatResponse:
    scope = await _resolve_scope(point_id=point_id, user=user, db=db)
    revenue = await get_revenue(
        period="week",
        point_id=point_id,
        user=user,
        db=db,
    )
    channels = await get_channels_analytics(
        period="week",
        point_id=point_id,
        user=user,
        db=db,
    )
    dishes = await get_dishes_analytics(
        period="week",
        point_id=point_id,
        limit=5,
        user=user,
        db=db,
    )
    anomalies = await get_anomalies(
        point_id=point_id,
        limit=5,
        user=user,
        db=db,
    )
    forecast = None
    if point_id is not None:
        forecast = await get_procurement_forecast(
            point_id=point_id,
            horizon_days=7,
            lookback_days=28,
            user=user,
            db=db,
        )

    evidence = _build_assistant_evidence(
        revenue=revenue,
        channels=channels,
        dishes=dishes,
        anomalies=anomalies,
        forecast=forecast,
    )
    suggestions = _build_assistant_suggestions(
        anomalies=anomalies,
        forecast=forecast,
        dishes=dishes,
    )
    fallback_answer = _build_fallback_answer(
        context_scope=scope.context_scope,
        evidence=evidence,
        anomalies=anomalies,
        suggestions=suggestions,
    )

    provider = build_ai_provider()
    system_prompt = (
        "Ты — ИИ-ассистент CRM-системы Japonica для управления ресторанной франшизой. "
        "Ты можешь отвечать на любые вопросы: общие, бытовые, аналитические. "
        "Если вопрос касается бизнеса, аналитики, выручки, заказов или склада — "
        "используй предоставленные данные CRM и давай конкретный управленческий вывод. "
        "Если вопрос общий или не связан с бизнесом — отвечай естественно и дружелюбно, "
        "как обычный умный ассистент, без навязывания аналитического контекста."
    )

    _analytics_keywords = (
        "выручк", "заказ", "склад", "остат", "аномал", "блюд", "прогноз",
        "канал", "продаж", "прибыл", "точк", "франчайз", "показател",
        "риск", "отчёт", "отчет", "сводк", "динамик", "падени", "рост",
        "revenue", "order", "stock", "forecast", "anomal",
    )
    question_lower = question.lower()
    is_analytics_question = any(kw in question_lower for kw in _analytics_keywords)

    if is_analytics_question and evidence:
        crm_context = "\n".join(
            [
                f"\nДанные CRM (контекст: {scope.context_scope}):",
                *[
                    f"- {item.label}: {item.value}"
                    + (f" ({item.detail})" if item.detail else "")
                    for item in evidence
                ],
                *(
                    ["Сигналы:"]
                    + [
                        f"- {signal.title}: {signal.description}. "
                        f"Текущее={signal.current_value}, базовое={signal.baseline_value or 'n/a'}"
                        for signal in anomalies.signals
                    ]
                    if anomalies.signals
                    else []
                ),
                *(
                    ["Рекомендации:"] + [f"- {s}" for s in suggestions]
                    if suggestions
                    else []
                ),
            ]
        )
        user_prompt = f"Вопрос: {question}{crm_context}"
    else:
        user_prompt = question

    try:
        completion = await provider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7 if not is_analytics_question else 0.2,
        )
        answer = completion.content.strip() or fallback_answer
        provider_name = completion.provider
        used_fallback = False
    except Exception as exc:
        logging.getLogger(__name__).error("AI provider error: %s", exc, exc_info=True)
        answer = fallback_answer
        provider_name = provider.provider
        used_fallback = True

    return AssistantChatResponse(
        answer=answer,
        provider=provider_name,
        used_fallback=used_fallback,
        evidence=evidence,
        suggestions=suggestions,
        context_scope=scope.context_scope,
    )


async def build_weekly_revenue_report_message(
    *,
    user: User,
    db: AsyncSession,
) -> str | None:
    scope = await _resolve_scope(point_id=None, user=user, db=db)
    if not scope.points:
        return None

    revenue = await get_revenue(period="week", point_id=None, user=user, db=db)
    channels = await get_channels_analytics(period="week", point_id=None, user=user, db=db)
    dishes = await get_dishes_analytics(
        period="week",
        point_id=None,
        limit=3,
        user=user,
        db=db,
    )

    total_revenue = sum((item.total_revenue for item in revenue), start=Decimal("0"))
    total_orders = sum((item.order_count for item in revenue), start=0)
    lines = [
        f"Еженедельный отчёт: {scope.context_scope}",
        f"Точек в отчёте: {len(scope.points)}",
        f"Выручка: {_money_text(total_revenue)}",
        f"Заказы: {total_orders}",
    ]
    if revenue:
        best_point = revenue[0]
        lines.append(
            f"Лучшая точка: {best_point.point_name} ({_money_text(best_point.total_revenue)})"
        )
    if channels:
        best_channel = channels[0]
        lines.append(
            f"Канал-лидер: {best_channel.source_channel} "
            f"({best_channel.order_count} заказов, {_money_text(best_channel.total_revenue)})"
        )
    if dishes.top:
        best_dish = dishes.top[0]
        lines.append(
            f"Топ-блюдо: {best_dish.dish_name} "
            f"({_quantity_text(best_dish.total_quantity)} порций)"
        )
    return "\n".join(lines)
