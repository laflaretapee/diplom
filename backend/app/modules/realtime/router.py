"""WebSocket real-time order queue endpoint."""
from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError
from sqlalchemy import select

from backend.app.core.security import decode_access_token
from backend.app.core.ws_manager import ws_manager
from backend.app.db.session import get_db_session
from backend.app.models.user import User, UserRole
from backend.app.models.user_point import UserPoint

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/orders/{point_id}")
async def ws_orders(
    point_id: uuid.UUID,
    ws: WebSocket,
    token: str = Query(...),
):
    # Authenticate via query param token
    try:
        payload = decode_access_token(token)
    except JWTError:
        await ws.close(code=4001)
        return

    user_id_str: str = payload.get("sub", "")
    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        await ws.close(code=4001)
        return

    # Verify point access
    async for db in get_db_session():
        result = await db.execute(select(User).where(User.id == user_uuid))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            await ws.close(code=4001)
            return

        if user.role != UserRole.SUPER_ADMIN:
            result2 = await db.execute(
                select(UserPoint).where(
                    UserPoint.user_id == user.id,
                    UserPoint.point_id == point_id,
                )
            )
            if result2.scalar_one_or_none() is None:
                await ws.close(code=4003)
                return
        break

    point_id_str = str(point_id)
    await ws_manager.connect(point_id_str, ws)
    try:
        await ws.send_json({"type": "connected", "point_id": point_id_str})
        while True:
            try:
                # Wait for ping interval or incoming message
                await asyncio.wait_for(ws.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                await ws.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(point_id_str, ws)
