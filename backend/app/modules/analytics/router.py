from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.deps import (
    require_any_role,
    require_franchisee_or_above,
    require_manager_or_above,
)
from backend.app.db.session import get_db_session
from backend.app.models.user import User
from backend.app.modules.analytics.schemas import (
    AnalyticsModuleStatus,
    AnalyticsSummaryResponse,
    AnomaliesResponse,
    AssistantChatRequest,
    AssistantChatResponse,
    ChannelAnalyticsItem,
    DishesAnalyticsResponse,
    ProcurementForecastResponse,
    RevenuePointItem,
)
from backend.app.modules.analytics.service import (
    answer_assistant_question,
    get_anomalies,
    get_channels_analytics,
    get_dishes_analytics,
    get_procurement_forecast,
    get_revenue,
    get_status,
    get_summary,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/status", response_model=AnalyticsModuleStatus)
async def analytics_status() -> AnalyticsModuleStatus:
    return get_status()


@router.get("/revenue", response_model=list[RevenuePointItem])
async def revenue_analytics(
    period: str = "week",
    point_id: uuid.UUID | None = None,
    user: User = Depends(require_franchisee_or_above),
    db: AsyncSession = Depends(get_db_session),
) -> list[RevenuePointItem]:
    return await get_revenue(period=period, point_id=point_id, user=user, db=db)


@router.get("/dishes", response_model=DishesAnalyticsResponse)
async def dishes_analytics(
    period: str = "week",
    point_id: uuid.UUID | None = None,
    limit: int = 10,
    user: User = Depends(require_franchisee_or_above),
    db: AsyncSession = Depends(get_db_session),
) -> DishesAnalyticsResponse:
    return await get_dishes_analytics(
        period=period,
        point_id=point_id,
        limit=limit,
        user=user,
        db=db,
    )


@router.get("/channels", response_model=list[ChannelAnalyticsItem])
async def channels_analytics(
    period: str = "week",
    point_id: uuid.UUID | None = None,
    user: User = Depends(require_franchisee_or_above),
    db: AsyncSession = Depends(get_db_session),
) -> list[ChannelAnalyticsItem]:
    return await get_channels_analytics(period=period, point_id=point_id, user=user, db=db)


@router.get("/summary", response_model=AnalyticsSummaryResponse)
async def analytics_summary(
    point_id: uuid.UUID,
    user: User = Depends(require_any_role),
    db: AsyncSession = Depends(get_db_session),
) -> AnalyticsSummaryResponse:
    return await get_summary(point_id=point_id, user=user, db=db)


@router.post("/assistant/chat", response_model=AssistantChatResponse)
async def analytics_assistant_chat(
    payload: AssistantChatRequest,
    user: User = Depends(require_franchisee_or_above),
    db: AsyncSession = Depends(get_db_session),
) -> AssistantChatResponse:
    return await answer_assistant_question(
        question=payload.question,
        point_id=payload.point_id,
        user=user,
        db=db,
    )


@router.get("/forecast", response_model=ProcurementForecastResponse)
async def procurement_forecast(
    point_id: uuid.UUID,
    horizon_days: int = 7,
    lookback_days: int = 28,
    user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db_session),
) -> ProcurementForecastResponse:
    return await get_procurement_forecast(
        point_id=point_id,
        horizon_days=horizon_days,
        lookback_days=lookback_days,
        user=user,
        db=db,
    )


@router.get("/anomalies", response_model=AnomaliesResponse)
async def analytics_anomalies(
    point_id: uuid.UUID | None = None,
    limit: int = 10,
    user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db_session),
) -> AnomaliesResponse:
    return await get_anomalies(
        point_id=point_id,
        limit=limit,
        user=user,
        db=db,
    )
