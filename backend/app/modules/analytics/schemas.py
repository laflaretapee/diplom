from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class AnalyticsModuleStatus(BaseModel):
    module: str
    status: str


class RevenuePointItem(BaseModel):
    point_id: uuid.UUID
    point_name: str
    total_revenue: Decimal
    order_count: int


class DishAnalyticsItem(BaseModel):
    dish_name: str
    total_quantity: Decimal
    total_revenue: Decimal


class DishesAnalyticsResponse(BaseModel):
    top: list[DishAnalyticsItem]
    bottom: list[DishAnalyticsItem]


class ChannelAnalyticsItem(BaseModel):
    source_channel: str
    order_count: int
    total_revenue: Decimal


class AnalyticsSummaryResponse(BaseModel):
    total_orders_today: int
    total_revenue_today: Decimal
    pending_orders: int
    top_dish_today: str | None


class AssistantChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    point_id: uuid.UUID | None = None


class AssistantEvidenceItem(BaseModel):
    label: str
    value: str
    detail: str | None = None


class AssistantChatResponse(BaseModel):
    answer: str
    provider: str
    used_fallback: bool
    evidence: list[AssistantEvidenceItem]
    suggestions: list[str]
    context_scope: str


class ForecastItem(BaseModel):
    ingredient_id: uuid.UUID
    ingredient_name: str
    unit: str
    current_stock: Decimal
    min_stock_level: Decimal
    avg_daily_usage: Decimal
    forecast_demand: Decimal
    recommended_purchase: Decimal


class ProcurementForecastResponse(BaseModel):
    point_id: uuid.UUID
    point_name: str
    horizon_days: int
    lookback_days: int
    generated_at: datetime
    items: list[ForecastItem]


class AnomalySignal(BaseModel):
    type: str
    severity: str
    title: str
    description: str
    metric: str
    current_value: str
    baseline_value: str | None = None
    point_id: uuid.UUID | None = None
    point_name: str | None = None


class AnomaliesResponse(BaseModel):
    generated_at: datetime
    signals: list[AnomalySignal]
