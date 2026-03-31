from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.deps import require_any_role, require_super_admin
from backend.app.db.session import get_db_session
from backend.app.models.point import Point
from backend.app.models.user import User
from backend.app.modules.franchisee.service import get_accessible_points_for_user

router = APIRouter(prefix="/points", tags=["points"])


class PaymentTypesUpdate(BaseModel):
    payment_types: list[str]


class PointRead(BaseModel):
    id: uuid.UUID
    name: str
    address: str
    is_active: bool
    franchisee_id: uuid.UUID | None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[PointRead])
async def list_points(
    user: User = Depends(require_any_role),
    db: AsyncSession = Depends(get_db_session),
) -> list[PointRead]:
    points = await get_accessible_points_for_user(db, user)
    return [PointRead.model_validate(point) for point in points]


@router.patch("/{point_id}/payment-types")
async def update_payment_types(
    point_id: uuid.UUID,
    data: PaymentTypesUpdate,
    user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    result = await db.execute(select(Point).where(Point.id == point_id))
    point = result.scalar_one_or_none()
    if point is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Point not found")
    point.payment_types = data.payment_types
    await db.commit()
    await db.refresh(point)
    return {
        "point_id": str(point.id),
        "payment_types": point.payment_types,
    }
