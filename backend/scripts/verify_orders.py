"""
Verify TASK-010 (orders API) and TASK-011 (payment types validation).
Runs directly against DB + app logic, no HTTP needed.
"""
import asyncio
import sys
from decimal import Decimal

sys.path.insert(0, "/workspace")

from sqlalchemy import select

from backend.app.db.session import SessionLocal
from backend.app.models.order import OrderStatus, PaymentType, SourceChannel
from backend.app.models.point import Point
from backend.app.modules.orders import service as order_service
from backend.app.modules.orders.schemas import OrderCreate, OrderItem, OrderStatusUpdate


async def main() -> None:
    async with SessionLocal() as db:
        # Find existing point
        result = await db.execute(select(Point).limit(1))
        point = result.scalar_one_or_none()
        if point is None:
            print("FAIL: No points found. Run verify_rbac.py first.")
            sys.exit(1)
        point_id = point.id
        print(f"Using point: {point.name} ({point_id})")

        # --- TASK-010: Create order ---
        create_data = OrderCreate(
            point_id=point_id,
            payment_type=PaymentType.CASH,
            source_channel=SourceChannel.POS,
            items=[OrderItem(name="Sushi", quantity=2, price=Decimal("350.00"))],
        )
        # Reset payment_types so any type is allowed
        point.payment_types = []
        await db.flush()

        order = await order_service.create_order(create_data, db)
        assert order.id is not None
        assert order.total_amount == Decimal("700.00"), f"Expected 700.00, got {order.total_amount}"
        assert order.status == OrderStatus.NEW
        print(f"PASS: Order created, id={order.id}, total={order.total_amount}, status={order.status}")

        # --- TASK-010: Status transitions ---
        # new -> in_progress
        upd = await order_service.update_order_status(
            order.id, OrderStatusUpdate(status=OrderStatus.IN_PROGRESS), db
        )
        assert upd.status == OrderStatus.IN_PROGRESS
        print(f"PASS: Status new->in_progress: {upd.status}")

        # in_progress -> ready
        upd = await order_service.update_order_status(
            order.id, OrderStatusUpdate(status=OrderStatus.READY), db
        )
        assert upd.status == OrderStatus.READY
        print(f"PASS: Status in_progress->ready: {upd.status}")

        # Invalid transition: ready -> new should fail
        try:
            await order_service.update_order_status(
                order.id, OrderStatusUpdate(status=OrderStatus.NEW), db
            )
            print("FAIL: ready->new should have raised HTTPException")
        except Exception as e:
            print(f"PASS: Invalid transition ready->new blocked: {e}")

        # --- TASK-010: List orders ---
        orders = await order_service.list_orders(point_id, db)
        assert len(orders) >= 1
        print(f"PASS: List orders by point_id: {len(orders)} order(s)")

        # Filter by status
        orders_ready = await order_service.list_orders(point_id, db, status=OrderStatus.READY)
        assert any(o.id == order.id for o in orders_ready)
        print(f"PASS: List orders filtered by status=ready: {len(orders_ready)} found")

        # --- TASK-011: Payment types validation ---
        # Set payment_types = ["cash"]
        await db.refresh(point)
        point.payment_types = ["cash"]
        await db.flush()

        # cash order should succeed
        cash_data = OrderCreate(
            point_id=point_id,
            payment_type=PaymentType.CASH,
            source_channel=SourceChannel.POS,
            items=[OrderItem(name="Roll", quantity=1, price=Decimal("200.00"))],
        )
        cash_order = await order_service.create_order(cash_data, db)
        print(f"PASS: cash order created when payment_types=['cash']: {cash_order.id}")

        # card order should fail
        card_data = OrderCreate(
            point_id=point_id,
            payment_type=PaymentType.CARD,
            source_channel=SourceChannel.POS,
            items=[OrderItem(name="Roll", quantity=1, price=Decimal("200.00"))],
        )
        try:
            await order_service.create_order(card_data, db)
            print("FAIL: card order should be rejected when payment_types=['cash']")
        except Exception as e:
            print(f"PASS: card order rejected when payment_types=['cash']: {e}")

        # Reset point payment_types back to empty
        point.payment_types = []
        await db.commit()

        print("\nAll order + payment type checks done.")


asyncio.run(main())
