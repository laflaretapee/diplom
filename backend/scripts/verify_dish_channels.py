from __future__ import annotations

import asyncio
import sys
import uuid
from decimal import Decimal
from pathlib import Path

import httpx
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import delete, select

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def main() -> None:
    from backend.app.core.config import get_settings
    from backend.app.db.session import SessionLocal
    from backend.app.main import app
    from backend.app.models.dish import DISH_SALES_CHANNELS, Dish
    from backend.app.models.order import Order, PaymentType, SourceChannel
    from backend.app.models.point import Point
    from backend.app.models.user import User, UserRole
    from backend.app.modules.auth.service import build_login_response
    from backend.app.modules.inbound import service as inbound_service
    from backend.app.modules.inbound.schemas import InboundOrderItem, InboundOrderRequest
    from backend.app.modules.warehouse import service as warehouse_service
    from backend.app.modules.warehouse.schemas import DishCreate, DishUpdate

    settings = get_settings()
    created_order_ids: list[uuid.UUID] = []
    created_dish_ids: list[uuid.UUID] = []

    async with SessionLocal() as db:
        try:
            admin_result = await db.execute(
                select(User)
                .where(User.role == UserRole.SUPER_ADMIN, User.is_active.is_(True))
                .limit(1)
            )
            admin = admin_result.scalar_one_or_none()
            expect(admin is not None, "No active super_admin found")

            point_result = await db.execute(select(Point).where(Point.is_active.is_(True)).limit(1))
            point = point_result.scalar_one_or_none()
            expect(point is not None, "No active point found")

            access_token, _ = build_login_response(admin)
            headers = {"Authorization": f"Bearer {access_token.access_token}"}
            website_pos_channels = [SourceChannel.WEBSITE.value, SourceChannel.POS.value]
            telegram_pos_channels = [SourceChannel.TELEGRAM.value, SourceChannel.POS.value]
            payment_type = (
                PaymentType(point.payment_types[0])
                if point.payment_types
                else PaymentType.CARD
            )

            dish_name = f"QA Dish Channels {uuid.uuid4().hex[:8]}"
            dish = await warehouse_service.create_dish(
                DishCreate(
                    name=dish_name,
                    description="verify dish channels",
                    price=Decimal("123.45"),
                ),
                db,
            )
            created_dish_ids.append(dish.id)
            print(f"Created dish: {dish.id}")

            expect(
                dish.available_channels == DISH_SALES_CHANNELS,
                "New dish must default to all sales channels",
            )
            print(f"PASS: new dish defaults to all channels {dish.available_channels}")

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                patch_response = await client.patch(
                    f"{settings.api_prefix}/warehouse/dishes/{dish.id}",
                    headers=headers,
                    json={"available_channels": [SourceChannel.POS.value, SourceChannel.WEBSITE.value]},
                )
                expect(
                    patch_response.status_code == 200,
                    f"PATCH failed: {patch_response.status_code} {patch_response.text}",
                )
                patch_payload = patch_response.json()
                expect(
                    patch_payload["available_channels"] == website_pos_channels,
                    f"Unexpected PATCH payload: {patch_payload}",
                )
                print("PASS: warehouse PATCH updates available_channels")

                list_response = await client.get(
                    f"{settings.api_prefix}/warehouse/dishes",
                    headers=headers,
                )
                expect(
                    list_response.status_code == 200,
                    f"GET /warehouse/dishes failed: {list_response.status_code}",
                )
                listed = next(
                    (item for item in list_response.json() if item["id"] == str(dish.id)),
                    None,
                )
                expect(listed is not None, "Updated dish not found in warehouse list response")
                expect(
                    listed["available_channels"] == website_pos_channels,
                    f"Unexpected list payload: {listed}",
                )
                print("PASS: warehouse GET exposes available_channels")

            await db.refresh(dish)
            refreshed = await warehouse_service.get_dish(dish.id, db)
            expect(
                refreshed.available_channels == website_pos_channels,
                f"Service read mismatch: {refreshed.available_channels}",
            )
            print("PASS: warehouse service reads persisted available_channels")

            reject_request = InboundOrderRequest(
                point_id=point.id,
                source_channel="telegram",
                payment_type=payment_type,
                items=[
                    InboundOrderItem(
                        dish_id=dish.id,
                        name=dish.name,
                        quantity=1,
                        price=Decimal("123.45"),
                    )
                ],
                notes="verify reject",
            )
            try:
                await inbound_service.create_inbound_order(reject_request, db)
                raise AssertionError(
                    "Inbound telegram order must be rejected for disabled dish channel"
                )
            except HTTPException as exc:
                expect(exc.status_code == 422, f"Unexpected reject status: {exc.status_code}")
                expect(
                    isinstance(exc.detail, dict),
                    f"Reject detail must be dict, got: {exc.detail!r}",
                )
                expect(
                    exc.detail.get("code") == "dish_channel_unavailable",
                    f"Unexpected reject detail: {exc.detail}",
                )
                expect(
                    exc.detail.get("source_channel") == SourceChannel.TELEGRAM.value,
                    f"Unexpected reject channel: {exc.detail}",
                )
                expect(
                    exc.detail.get("dish_id") == str(dish.id),
                    f"Unexpected reject dish_id: {exc.detail}",
                )
                print("PASS: inbound rejects disabled sales channel with 422 detail payload")

            review_dish = await warehouse_service.create_dish(
                DishCreate(
                    name=f"QA Dish Review {uuid.uuid4().hex[:8]}",
                    description="mismatch guard",
                    price=Decimal("99.00"),
                    available_channels=[SourceChannel.TELEGRAM],
                ),
                db,
            )
            created_dish_ids.append(review_dish.id)

            try:
                mismatch_request = InboundOrderRequest(
                    point_id=point.id,
                    source_channel="telegram",
                    payment_type=payment_type,
                    items=[
                        InboundOrderItem(
                            dish_id=review_dish.id,
                            name=dish.name,
                            quantity=1,
                            price=Decimal("99.00"),
                        )
                    ],
                )
                await inbound_service.create_inbound_order(mismatch_request, db)
                raise AssertionError("Inbound request with mismatched dish_id/name must be rejected")
            except HTTPException as exc:
                expect(exc.status_code == 422, f"Unexpected mismatch status: {exc.status_code}")
                expect(
                    isinstance(exc.detail, dict) and exc.detail.get("code") == "dish_identity_mismatch",
                    f"Unexpected mismatch detail: {exc.detail}",
                )
                print("PASS: inbound rejects mismatched dish_id and name")

            try:
                InboundOrderRequest(
                    point_id=point.id,
                    source_channel="pos",
                    payment_type=payment_type,
                    items=[
                        InboundOrderItem(
                            dish_id=dish.id,
                            name=dish.name,
                            quantity=1,
                            price=Decimal("123.45"),
                        )
                    ],
                )
                raise AssertionError("Inbound schema must reject POS channel")
            except ValidationError:
                print("PASS: inbound schema rejects POS channel")

            await warehouse_service.update_dish(
                dish.id,
                DishUpdate(available_channels=[SourceChannel.POS.value, SourceChannel.TELEGRAM.value]),
                db,
            )
            enabled_for_telegram = await warehouse_service.get_dish(dish.id, db)
            expect(
                enabled_for_telegram.available_channels == telegram_pos_channels,
                f"Unexpected telegram-enabled channels: {enabled_for_telegram.available_channels}",
            )

            accept_request = InboundOrderRequest(
                point_id=point.id,
                source_channel="telegram",
                payment_type=payment_type,
                items=[
                    InboundOrderItem(
                        name=dish.name,
                        quantity=2,
                        price=Decimal("123.45"),
                    )
                ],
                notes="verify accept",
            )
            accepted_order = await inbound_service.create_inbound_order(accept_request, db)
            created_order_ids.append(accepted_order.id)
            expect(
                accepted_order.source_channel == SourceChannel.TELEGRAM,
                "Accepted inbound order has wrong source_channel",
            )
            print(f"PASS: inbound accepts enabled sales channel, order={accepted_order.id}")

            print("\nDish channel verification completed successfully.")
        finally:
            if created_order_ids:
                await db.execute(delete(Order).where(Order.id.in_(created_order_ids)))
            if created_dish_ids:
                await db.execute(delete(Dish).where(Dish.id.in_(created_dish_ids)))
            await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
