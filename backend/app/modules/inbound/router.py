from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.core.rate_limit import RateLimitPolicy, rate_limit
from backend.app.db.session import get_db_session
from backend.app.modules.inbound import service
from backend.app.modules.inbound.schemas import InboundOrderRequest, InboundOrderResponse

router = APIRouter(prefix="/inbound", tags=["inbound"])


def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if x_api_key != settings.inbound_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


@router.post(
    "/orders",
    response_model=InboundOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_inbound_order(
    data: InboundOrderRequest,
    _: None = Depends(verify_api_key),
    __: None = rate_limit(
        RateLimitPolicy(
            bucket="inbound-orders",
            limit=get_settings().inbound_rate_limit_requests,
            window_seconds=get_settings().inbound_rate_limit_window_seconds,
        )
    ),
    db: AsyncSession = Depends(get_db_session),
) -> InboundOrderResponse:
    order = await service.create_inbound_order(data, db)
    return InboundOrderResponse.model_validate(order)
