from __future__ import annotations

import asyncio
import json
import sys
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.security import hash_password
from backend.app.db.session import SessionLocal
from backend.app.models.dish import Dish
from backend.app.models.dish_ingredient import DishIngredient
from backend.app.models.franchisee import Franchisee, FranchiseeStatus
from backend.app.models.franchisee_task import FranchiseeTask, TaskStatus
from backend.app.models.ingredient import Ingredient
from backend.app.models.order import (
    Order,
    OrderStatus,
    PaymentStatus,
    PaymentType,
    SourceChannel,
)
from backend.app.models.point import Point
from backend.app.models.stock_item import StockItem
from backend.app.models.stock_movement import MovementType, StockMovement
from backend.app.models.user import User, UserRole
from backend.app.models.user_point import UserPoint

DEMO_PREFIX = "[DEMO]"
DEMO_NAMESPACE = uuid.UUID("d934c7db-3aa1-4946-bf37-469690e82f55")
PAYMENT_TYPES = [payment.value for payment in PaymentType]


@dataclass(frozen=True)
class UserSeed:
    key: str
    email: str
    password: str
    name: str
    role: UserRole


@dataclass(frozen=True)
class FranchiseeSeed:
    key: str
    company_name: str
    contact_name: str
    contact_email: str
    contact_phone: str
    status: FranchiseeStatus
    owner_user_key: str
    notes: list[dict[str, str]]


@dataclass(frozen=True)
class PointSeed:
    key: str
    name: str
    address: str
    franchisee_key: str
    opened_days_ago: int


@dataclass(frozen=True)
class IngredientSeed:
    key: str
    name: str
    unit: str
    min_stock_level: Decimal


@dataclass(frozen=True)
class DishSeed:
    key: str
    name: str
    description: str
    price: Decimal
    recipe: dict[str, Decimal]


@dataclass(frozen=True)
class OrderSeed:
    key: str
    point_key: str
    days_ago: int
    hour: int
    minute: int
    status: OrderStatus
    payment_type: PaymentType
    payment_status: PaymentStatus
    source_channel: SourceChannel
    items: list[tuple[str, int]]
    notes: str | None = None


USERS: tuple[UserSeed, ...] = (
    UserSeed(
        key="admin",
        email="admin@japonica.example.com",
        password="Admin1234!",
        name="Japonica Demo Admin",
        role=UserRole.SUPER_ADMIN,
    ),
    UserSeed(
        key="franchisee_ufa1",
        email="franchisee-ufa1@japonica.example.com",
        password="Demo1234!",
        name="Japonica Demo Franchisee Ufa",
        role=UserRole.FRANCHISEE,
    ),
    UserSeed(
        key="manager_ufa1",
        email="manager-ufa1@japonica.example.com",
        password="Demo1234!",
        name="Japonica Demo Manager Ufa 1",
        role=UserRole.POINT_MANAGER,
    ),
    UserSeed(
        key="staff_ufa1",
        email="staff-ufa1@japonica.example.com",
        password="Demo1234!",
        name="Japonica Demo Staff Ufa 1",
        role=UserRole.STAFF,
    ),
)

FRANCHISEES: tuple[FranchiseeSeed, ...] = (
    FranchiseeSeed(
        key="ufa_active",
        company_name=f"{DEMO_PREFIX} Ufa Family Franchise",
        contact_name="Aidar Karimov",
        contact_email="ufa-owner@japonica.example.com",
        contact_phone="+7-900-100-10-10",
        status=FranchiseeStatus.ACTIVE,
        owner_user_key="franchisee_ufa1",
        notes=[
            {
                "id": str(uuid.uuid5(DEMO_NAMESPACE, "note:ufa_active:0")),
                "text": "Основной demo-франчайзи для показа кабинета партнера.",
                "author": "Japonica Demo Admin",
                "created_at": "2026-03-01T08:00:00+00:00",
            }
        ],
    ),
    FranchiseeSeed(
        key="samara_negotiation",
        company_name=f"{DEMO_PREFIX} Samara Prospect",
        contact_name="Elena Voronina",
        contact_email="samara-prospect@japonica.example.com",
        contact_phone="+7-900-200-20-20",
        status=FranchiseeStatus.NEGOTIATION,
        owner_user_key="admin",
        notes=[
            {
                "id": str(uuid.uuid5(DEMO_NAMESPACE, "note:samara_negotiation:0")),
                "text": "Ожидаем финальное коммерческое предложение и пакет документов.",
                "author": "Japonica Demo Admin",
                "created_at": "2026-03-10T09:30:00+00:00",
            }
        ],
    ),
    FranchiseeSeed(
        key="perm_training",
        company_name=f"{DEMO_PREFIX} Perm Training Cohort",
        contact_name="Maksim Belyaev",
        contact_email="perm-training@japonica.example.com",
        contact_phone="+7-900-300-30-30",
        status=FranchiseeStatus.TRAINING,
        owner_user_key="admin",
        notes=[
            {
                "id": str(uuid.uuid5(DEMO_NAMESPACE, "note:perm_training:0")),
                "text": "Команда проходит онбординг и обучение по стандартам кухни.",
                "author": "Japonica Demo Admin",
                "created_at": "2026-03-15T11:00:00+00:00",
            }
        ],
    ),
)

POINTS: tuple[PointSeed, ...] = (
    PointSeed(
        key="ufa1",
        name=f"{DEMO_PREFIX} Ufa 1",
        address="Ufa, Prospekt Oktyabrya 12",
        franchisee_key="ufa_active",
        opened_days_ago=180,
    ),
    PointSeed(
        key="ufa2",
        name=f"{DEMO_PREFIX} Ufa 2",
        address="Ufa, Aksakova 4",
        franchisee_key="ufa_active",
        opened_days_ago=120,
    ),
    PointSeed(
        key="perm1",
        name=f"{DEMO_PREFIX} Perm Pilot",
        address="Perm, Lenina 55",
        franchisee_key="perm_training",
        opened_days_ago=30,
    ),
)

INGREDIENTS: tuple[IngredientSeed, ...] = (
    IngredientSeed("rice", f"{DEMO_PREFIX} Rice", "kg", Decimal("6.000")),
    IngredientSeed("nori", f"{DEMO_PREFIX} Nori", "pcs", Decimal("40.000")),
    IngredientSeed("salmon", f"{DEMO_PREFIX} Salmon", "kg", Decimal("3.500")),
    IngredientSeed("tuna", f"{DEMO_PREFIX} Tuna", "kg", Decimal("2.500")),
    IngredientSeed("shrimp", f"{DEMO_PREFIX} Shrimp", "kg", Decimal("2.200")),
    IngredientSeed("eel", f"{DEMO_PREFIX} Eel", "kg", Decimal("1.800")),
    IngredientSeed("cream_cheese", f"{DEMO_PREFIX} Cream Cheese", "kg", Decimal("2.000")),
    IngredientSeed("cucumber", f"{DEMO_PREFIX} Cucumber", "kg", Decimal("2.500")),
    IngredientSeed("avocado", f"{DEMO_PREFIX} Avocado", "kg", Decimal("1.600")),
    IngredientSeed("tempura_flakes", f"{DEMO_PREFIX} Tempura Flakes", "kg", Decimal("1.200")),
    IngredientSeed("miso_paste", f"{DEMO_PREFIX} Miso Paste", "kg", Decimal("1.100")),
    IngredientSeed("green_tea", f"{DEMO_PREFIX} Green Tea", "l", Decimal("4.000")),
)

DISHES: tuple[DishSeed, ...] = (
    DishSeed(
        "philadelphia",
        f"{DEMO_PREFIX} Philadelphia",
        "Classic salmon roll for demo analytics.",
        Decimal("420.00"),
        {
            "rice": Decimal("0.180"),
            "nori": Decimal("1.000"),
            "salmon": Decimal("0.090"),
            "cream_cheese": Decimal("0.050"),
            "cucumber": Decimal("0.030"),
        },
    ),
    DishSeed(
        "california",
        f"{DEMO_PREFIX} California Crab",
        "Demo bestseller with avocado and cucumber.",
        Decimal("390.00"),
        {
            "rice": Decimal("0.170"),
            "nori": Decimal("1.000"),
            "avocado": Decimal("0.040"),
            "cucumber": Decimal("0.025"),
            "shrimp": Decimal("0.045"),
        },
    ),
    DishSeed(
        "salmon_nigiri",
        f"{DEMO_PREFIX} Salmon Nigiri",
        "Compact dish to support top/bottom analytics.",
        Decimal("280.00"),
        {
            "rice": Decimal("0.080"),
            "salmon": Decimal("0.045"),
        },
    ),
    DishSeed(
        "shrimp_tempura",
        f"{DEMO_PREFIX} Shrimp Tempura Roll",
        "Warm roll for warehouse forecast calculations.",
        Decimal("450.00"),
        {
            "rice": Decimal("0.180"),
            "nori": Decimal("1.000"),
            "shrimp": Decimal("0.090"),
            "tempura_flakes": Decimal("0.030"),
            "cream_cheese": Decimal("0.040"),
        },
    ),
    DishSeed(
        "dragon",
        f"{DEMO_PREFIX} Dragon Roll",
        "Eel-driven premium roll.",
        Decimal("480.00"),
        {
            "rice": Decimal("0.190"),
            "nori": Decimal("1.000"),
            "eel": Decimal("0.085"),
            "avocado": Decimal("0.040"),
            "cucumber": Decimal("0.020"),
        },
    ),
    DishSeed(
        "miso",
        f"{DEMO_PREFIX} Miso Soup",
        "Low-price dish for bottom analytics examples.",
        Decimal("190.00"),
        {
            "miso_paste": Decimal("0.040"),
            "green_tea": Decimal("0.150"),
        },
    ),
    DishSeed(
        "poke",
        f"{DEMO_PREFIX} Tuna Poke",
        "Bowl dish for average check variation.",
        Decimal("510.00"),
        {
            "rice": Decimal("0.160"),
            "tuna": Decimal("0.090"),
            "avocado": Decimal("0.050"),
            "cucumber": Decimal("0.040"),
        },
    ),
    DishSeed(
        "tea",
        f"{DEMO_PREFIX} Sencha Tea",
        "Simple add-on item for demo orders.",
        Decimal("120.00"),
        {
            "green_tea": Decimal("0.250"),
        },
    ),
)

ORDERS: tuple[OrderSeed, ...] = (
    OrderSeed("ufa1-26", "ufa1", 26, 13, 15, OrderStatus.DELIVERED, PaymentType.CARD, PaymentStatus.PAID, SourceChannel.POS, [("philadelphia", 2), ("tea", 2)]),
    OrderSeed("ufa2-23", "ufa2", 23, 12, 40, OrderStatus.DELIVERED, PaymentType.CARD, PaymentStatus.PAID, SourceChannel.WEBSITE, [("california", 2), ("miso", 1)]),
    OrderSeed("perm1-21", "perm1", 21, 18, 20, OrderStatus.DELIVERED, PaymentType.ONLINE, PaymentStatus.PAID, SourceChannel.MOBILE_APP, [("poke", 1), ("tea", 1)]),
    OrderSeed("ufa1-13", "ufa1", 13, 12, 5, OrderStatus.DELIVERED, PaymentType.CARD, PaymentStatus.PAID, SourceChannel.WEBSITE, [("dragon", 3), ("tea", 2)], "Strong prior-week lunch"),
    OrderSeed("ufa1-11", "ufa1", 11, 19, 10, OrderStatus.DELIVERED, PaymentType.CASH, PaymentStatus.PAID, SourceChannel.POS, [("shrimp_tempura", 4), ("miso", 2)]),
    OrderSeed("ufa1-9", "ufa1", 9, 14, 30, OrderStatus.DELIVERED, PaymentType.ONLINE, PaymentStatus.PAID, SourceChannel.MOBILE_APP, [("philadelphia", 4), ("california", 2)]),
    OrderSeed("ufa2-10", "ufa2", 10, 13, 50, OrderStatus.DELIVERED, PaymentType.CARD, PaymentStatus.PAID, SourceChannel.TELEGRAM, [("california", 3), ("tea", 2)]),
    OrderSeed("ufa2-8", "ufa2", 8, 17, 5, OrderStatus.DELIVERED, PaymentType.ONLINE, PaymentStatus.PAID, SourceChannel.WEBSITE, [("poke", 2), ("miso", 2)]),
    OrderSeed("perm1-7", "perm1", 7, 16, 45, OrderStatus.DELIVERED, PaymentType.CARD, PaymentStatus.PAID, SourceChannel.VK, [("salmon_nigiri", 3), ("tea", 2)]),
    OrderSeed("ufa1-6", "ufa1", 6, 12, 25, OrderStatus.DELIVERED, PaymentType.CARD, PaymentStatus.PAID, SourceChannel.WEBSITE, [("miso", 2), ("tea", 3)], "Intentional revenue drop window"),
    OrderSeed("ufa2-5", "ufa2", 5, 19, 35, OrderStatus.DELIVERED, PaymentType.CARD, PaymentStatus.PAID, SourceChannel.POS, [("dragon", 2), ("philadelphia", 1)]),
    OrderSeed("perm1-4", "perm1", 4, 15, 15, OrderStatus.CANCELLED, PaymentType.CASH, PaymentStatus.REFUNDED, SourceChannel.POS, [("miso", 2)]),
    OrderSeed("ufa1-3", "ufa1", 3, 18, 55, OrderStatus.IN_PROGRESS, PaymentType.ONLINE, PaymentStatus.PAID, SourceChannel.TELEGRAM, [("salmon_nigiri", 2), ("tea", 1)]),
    OrderSeed("ufa2-2", "ufa2", 2, 13, 20, OrderStatus.DELIVERED, PaymentType.ONLINE, PaymentStatus.PAID, SourceChannel.MOBILE_APP, [("shrimp_tempura", 2), ("tea", 1)]),
    OrderSeed("ufa1-1", "ufa1", 1, 20, 5, OrderStatus.READY, PaymentType.CARD, PaymentStatus.PAID, SourceChannel.POS, [("philadelphia", 1), ("miso", 1)]),
    OrderSeed("ufa1-today-1", "ufa1", 0, 11, 0, OrderStatus.DELIVERED, PaymentType.CARD, PaymentStatus.PAID, SourceChannel.WEBSITE, [("philadelphia", 2), ("tea", 1)]),
    OrderSeed("ufa1-today-2", "ufa1", 0, 15, 30, OrderStatus.NEW, PaymentType.CASH, PaymentStatus.PENDING, SourceChannel.POS, [("california", 1), ("miso", 1)]),
    OrderSeed("perm1-today", "perm1", 0, 13, 10, OrderStatus.DELIVERED, PaymentType.ONLINE, PaymentStatus.PAID, SourceChannel.MOBILE_APP, [("poke", 1)]),
)

FRANCHISEE_TASKS: dict[str, list[dict[str, object]]] = {
    "ufa_active": [
        {"key": "ufa-contract", "title": "Подтвердить квартальный план продаж", "stage": FranchiseeStatus.ACTIVE, "status": TaskStatus.DONE, "due_in_days": -10, "created_days_ago": 20, "completed_days_ago": 12},
        {"key": "ufa-hiring", "title": "Закрыть вакансию второго сушиста", "stage": FranchiseeStatus.ACTIVE, "status": TaskStatus.IN_PROGRESS, "due_in_days": 3, "created_days_ago": 2, "completed_days_ago": None},
    ],
    "samara_negotiation": [
        {"key": "samara-call", "title": "Провести финальный звонок по договору", "stage": FranchiseeStatus.NEGOTIATION, "status": TaskStatus.PENDING, "due_in_days": 2, "created_days_ago": 4, "completed_days_ago": None},
        {"key": "samara-unit", "title": "Согласовать список оборудования", "stage": FranchiseeStatus.NEGOTIATION, "status": TaskStatus.IN_PROGRESS, "due_in_days": 5, "created_days_ago": 6, "completed_days_ago": None},
    ],
    "perm_training": [
        {"key": "perm-training-manual", "title": "Пройти экзамен по стандартам кухни", "stage": FranchiseeStatus.TRAINING, "status": TaskStatus.DONE, "due_in_days": -2, "created_days_ago": 10, "completed_days_ago": 1},
        {"key": "perm-shift", "title": "Собрать первую тестовую смену", "stage": FranchiseeStatus.TRAINING, "status": TaskStatus.PENDING, "due_in_days": 4, "created_days_ago": 3, "completed_days_ago": None},
    ],
}


def demo_uuid(kind: str, key: str) -> uuid.UUID:
    return uuid.uuid5(DEMO_NAMESPACE, f"{kind}:{key}")


def anchor_at(days_ago: int, hour: int, minute: int = 0) -> datetime:
    day = datetime.now(UTC).date() - timedelta(days=days_ago)
    return datetime.combine(day, time(hour=hour, minute=minute), tzinfo=UTC)


def ensure_root_path() -> None:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))


def tagged_name_filter(column) -> object:
    return column.like(f"{DEMO_PREFIX}%")


async def _collect_ids(db: AsyncSession, model, filters: Iterable[object]) -> set[uuid.UUID]:
    clauses = [clause for clause in filters if clause is not None]
    if not clauses:
        return set()
    result = await db.execute(select(model.id).where(or_(*clauses)))
    return {row[0] for row in result.all()}


async def cleanup_owned_demo_graph(db: AsyncSession) -> None:
    user_ids = await _collect_ids(
        db,
        User,
        [User.email.in_([item.email for item in USERS])],
    )
    franchisee_ids = await _collect_ids(
        db,
        Franchisee,
        [tagged_name_filter(Franchisee.company_name)],
    )
    point_ids = await _collect_ids(
        db,
        Point,
        [tagged_name_filter(Point.name)],
    )
    await _collect_ids(
        db,
        Ingredient,
        [tagged_name_filter(Ingredient.name)],
    )
    dish_ids = await _collect_ids(
        db,
        Dish,
        [tagged_name_filter(Dish.name)],
    )

    stock_item_ids: set[uuid.UUID] = set()
    if point_ids:
        result = await db.execute(select(StockItem.id).where(StockItem.point_id.in_(point_ids)))
        stock_item_ids = {row[0] for row in result.all()}

    if stock_item_ids:
        await db.execute(delete(StockMovement).where(StockMovement.stock_item_id.in_(stock_item_ids)))
    if point_ids:
        await db.execute(delete(Order).where(Order.point_id.in_(point_ids)))
        await db.execute(delete(UserPoint).where(UserPoint.point_id.in_(point_ids)))
    if user_ids:
        await db.execute(delete(UserPoint).where(UserPoint.user_id.in_(user_ids)))
    if franchisee_ids:
        await db.execute(delete(FranchiseeTask).where(FranchiseeTask.franchisee_id.in_(franchisee_ids)))
    if dish_ids:
        await db.execute(delete(DishIngredient).where(DishIngredient.dish_id.in_(dish_ids)))
    if stock_item_ids:
        await db.execute(delete(StockItem).where(StockItem.id.in_(stock_item_ids)))
    await db.flush()


async def _merge_entities(db: AsyncSession, items: Iterable[object]) -> None:
    for item in items:
        await db.merge(item)
    await db.flush()


def build_users() -> dict[str, User]:
    created_at = anchor_at(28, 8, 0)
    users: dict[str, User] = {}
    for item in USERS:
        users[item.key] = User(
            id=demo_uuid("user", item.key),
            email=item.email,
            password_hash=hash_password(item.password),
            name=item.name,
            role=item.role,
            notification_settings={
                "franchisee_stage_changed": True,
                "franchisee_task_changed": True,
                "franchisee_task_overdue": True,
                "order_created": True,
                "order_cancelled": True,
                "low_stock": True,
            },
            is_active=True,
            created_at=created_at,
            updated_at=created_at,
        )
    return users


def build_franchisees(users: dict[str, User]) -> dict[str, Franchisee]:
    franchisees: dict[str, Franchisee] = {}
    for index, item in enumerate(FRANCHISEES):
        created_at = anchor_at(26 - index * 3, 10, 0)
        franchisees[item.key] = Franchisee(
            id=demo_uuid("franchisee", item.key),
            company_name=item.company_name,
            contact_name=item.contact_name,
            contact_email=item.contact_email,
            contact_phone=item.contact_phone,
            status=item.status,
            responsible_owner_id=users[item.owner_user_key].id,
            notes=json.dumps(item.notes, ensure_ascii=False),
            created_at=created_at,
            updated_at=created_at,
        )
    return franchisees


def build_points(franchisees: dict[str, Franchisee]) -> dict[str, Point]:
    points: dict[str, Point] = {}
    for item in POINTS:
        created_at = anchor_at(20, 9, 0)
        opened_at = (datetime.now(UTC).date() - timedelta(days=item.opened_days_ago))
        points[item.key] = Point(
            id=demo_uuid("point", item.key),
            franchisee_id=franchisees[item.franchisee_key].id,
            name=item.name,
            address=item.address,
            payment_types=list(PAYMENT_TYPES),
            is_active=True,
            opened_at=opened_at,
            created_at=created_at,
            updated_at=created_at,
        )
    return points


def build_ingredients() -> dict[str, Ingredient]:
    created_at = anchor_at(28, 7, 30)
    ingredients: dict[str, Ingredient] = {}
    for item in INGREDIENTS:
        ingredients[item.key] = Ingredient(
            id=demo_uuid("ingredient", item.key),
            name=item.name,
            unit=item.unit,
            min_stock_level=item.min_stock_level,
            is_active=True,
            created_at=created_at,
            updated_at=created_at,
        )
    return ingredients


def build_dishes() -> dict[str, Dish]:
    created_at = anchor_at(28, 8, 15)
    dishes: dict[str, Dish] = {}
    for item in DISHES:
        dishes[item.key] = Dish(
            id=demo_uuid("dish", item.key),
            name=item.name,
            description=item.description,
            price=item.price,
            is_active=True,
            created_at=created_at,
            updated_at=created_at,
        )
    return dishes


def build_dish_ingredients(
    dishes: dict[str, Dish],
    ingredients: dict[str, Ingredient],
) -> list[DishIngredient]:
    created: list[DishIngredient] = []
    for dish_seed in DISHES:
        for ingredient_key, quantity in dish_seed.recipe.items():
            created.append(
                DishIngredient(
                    id=demo_uuid("dish_ingredient", f"{dish_seed.key}:{ingredient_key}"),
                    dish_id=dishes[dish_seed.key].id,
                    ingredient_id=ingredients[ingredient_key].id,
                    quantity_per_portion=quantity,
                )
            )
    return created


def build_user_points(users: dict[str, User], points: dict[str, Point]) -> list[UserPoint]:
    return [
        UserPoint(user_id=users["manager_ufa1"].id, point_id=points["ufa1"].id),
        UserPoint(user_id=users["staff_ufa1"].id, point_id=points["ufa1"].id),
    ]


def build_stock_items(points: dict[str, Point], ingredients: dict[str, Ingredient]) -> dict[tuple[str, str], StockItem]:
    stock_items: dict[tuple[str, str], StockItem] = {}
    for point_key in points:
        for ingredient_key in ingredients:
            item_id = demo_uuid("stock_item", f"{point_key}:{ingredient_key}")
            created_at = anchor_at(28, 6, 0)
            stock_items[(point_key, ingredient_key)] = StockItem(
                id=item_id,
                ingredient_id=ingredients[ingredient_key].id,
                point_id=points[point_key].id,
                quantity=Decimal("0"),
                updated_at=created_at,
            )
    return stock_items


def movement_quantity(stock_item: StockItem, movement_type: MovementType, quantity: Decimal) -> None:
    if movement_type == MovementType.IN:
        stock_item.quantity += quantity
    elif movement_type == MovementType.OUT:
        stock_item.quantity -= quantity
    else:
        stock_item.quantity = quantity


def append_movement(
    movements: list[StockMovement],
    stock_items: dict[tuple[str, str], StockItem],
    *,
    point_key: str,
    ingredient_key: str,
    movement_type: MovementType,
    quantity: Decimal,
    days_ago: int,
    hour: int,
    minute: int,
    reason: str,
    created_by_id: uuid.UUID | None,
) -> None:
    stock_item = stock_items[(point_key, ingredient_key)]
    created_at = anchor_at(days_ago, hour, minute)
    movement_quantity(stock_item, movement_type, quantity)
    stock_item.updated_at = created_at
    movements.append(
        StockMovement(
            id=demo_uuid(
                "stock_movement",
                f"{point_key}:{ingredient_key}:{movement_type.value}:{days_ago}:{hour}:{minute}:{reason}",
            ),
            stock_item_id=stock_item.id,
            movement_type=movement_type,
            quantity=quantity,
            reason=reason,
            created_at=created_at,
            created_by_id=created_by_id,
        )
    )


def build_stock_movements(
    stock_items: dict[tuple[str, str], StockItem],
    users: dict[str, User],
) -> list[StockMovement]:
    manager_id = users["manager_ufa1"].id
    admin_id = users["admin"].id
    movements: list[StockMovement] = []

    for point_key in ("ufa1", "ufa2", "perm1"):
        for ingredient_key in (
            "rice",
            "nori",
            "salmon",
            "tuna",
            "shrimp",
            "eel",
            "cream_cheese",
            "cucumber",
            "avocado",
            "tempura_flakes",
            "miso_paste",
            "green_tea",
        ):
            base_qty = {
                "rice": Decimal("18.000"),
                "nori": Decimal("180.000"),
                "salmon": Decimal("9.000"),
                "tuna": Decimal("6.000"),
                "shrimp": Decimal("7.000"),
                "eel": Decimal("4.500"),
                "cream_cheese": Decimal("5.000"),
                "cucumber": Decimal("6.500"),
                "avocado": Decimal("4.500"),
                "tempura_flakes": Decimal("2.000"),
                "miso_paste": Decimal("1.500"),
                "green_tea": Decimal("9.000"),
            }[ingredient_key]
            append_movement(
                movements,
                stock_items,
                point_key=point_key,
                ingredient_key=ingredient_key,
                movement_type=MovementType.IN,
                quantity=base_qty,
                days_ago=28,
                hour=8,
                minute=0,
                reason="Initial demo stock",
                created_by_id=admin_id,
            )

    for point_key in ("ufa1", "ufa2", "perm1"):
        append_movement(movements, stock_items, point_key=point_key, ingredient_key="rice", movement_type=MovementType.IN, quantity=Decimal("6.000"), days_ago=15, hour=9, minute=30, reason="Weekly rice supply", created_by_id=admin_id)
        append_movement(movements, stock_items, point_key=point_key, ingredient_key="salmon", movement_type=MovementType.IN, quantity=Decimal("2.500"), days_ago=15, hour=9, minute=45, reason="Weekly salmon supply", created_by_id=admin_id)
        append_movement(movements, stock_items, point_key=point_key, ingredient_key="green_tea", movement_type=MovementType.IN, quantity=Decimal("3.000"), days_ago=12, hour=10, minute=0, reason="Beverage top-up", created_by_id=admin_id)

    append_movement(movements, stock_items, point_key="ufa1", ingredient_key="salmon", movement_type=MovementType.OUT, quantity=Decimal("4.200"), days_ago=3, hour=21, minute=0, reason="manual_writeoff:quality_issue", created_by_id=manager_id)
    append_movement(movements, stock_items, point_key="ufa1", ingredient_key="rice", movement_type=MovementType.OUT, quantity=Decimal("11.500"), days_ago=2, hour=21, minute=10, reason="manual_writeoff:line_check", created_by_id=manager_id)
    append_movement(movements, stock_items, point_key="ufa1", ingredient_key="green_tea", movement_type=MovementType.OUT, quantity=Decimal("0.900"), days_ago=2, hour=21, minute=15, reason="manual_writeoff:service_loss", created_by_id=manager_id)
    append_movement(movements, stock_items, point_key="ufa1", ingredient_key="miso_paste", movement_type=MovementType.OUT, quantity=Decimal("0.350"), days_ago=18, hour=20, minute=20, reason="manual_writeoff:training", created_by_id=manager_id)
    append_movement(movements, stock_items, point_key="ufa2", ingredient_key="rice", movement_type=MovementType.OUT, quantity=Decimal("1.200"), days_ago=16, hour=20, minute=0, reason="manual_writeoff:trial", created_by_id=admin_id)
    append_movement(movements, stock_items, point_key="perm1", ingredient_key="green_tea", movement_type=MovementType.ADJUSTMENT, quantity=Decimal("8.500"), days_ago=5, hour=18, minute=0, reason="inventory_count", created_by_id=admin_id)

    return movements


def build_orders(points: dict[str, Point], dishes: dict[str, Dish]) -> list[Order]:
    created: list[Order] = []
    for item in ORDERS:
        created_at = anchor_at(item.days_ago, item.hour, item.minute)
        payload_items = []
        total_amount = Decimal("0")
        for dish_key, quantity in item.items:
            dish = dishes[dish_key]
            payload_items.append(
                {
                    "dish_id": str(dish.id),
                    "name": dish.name,
                    "quantity": quantity,
                    "price": str(dish.price),
                }
            )
            total_amount += dish.price * quantity
        created.append(
            Order(
                id=demo_uuid("order", item.key),
                point_id=points[item.point_key].id,
                status=item.status,
                payment_type=item.payment_type,
                payment_status=item.payment_status,
                source_channel=item.source_channel,
                items=payload_items,
                total_amount=total_amount,
                notes=item.notes,
                created_at=created_at,
                updated_at=created_at,
            )
        )
    return created


def build_franchisee_tasks(franchisees: dict[str, Franchisee]) -> list[FranchiseeTask]:
    tasks: list[FranchiseeTask] = []
    today = datetime.now(UTC).date()
    for franchisee_key, items in FRANCHISEE_TASKS.items():
        for item in items:
            created_at = anchor_at(int(item["created_days_ago"]), 9, 0)
            completed_days_ago = item["completed_days_ago"]
            completed_at = (
                anchor_at(int(completed_days_ago), 18, 0)
                if completed_days_ago is not None
                else None
            )
            due_date = today + timedelta(days=int(item["due_in_days"]))
            tasks.append(
                FranchiseeTask(
                    id=demo_uuid("franchisee_task", str(item["key"])),
                    franchisee_id=franchisees[franchisee_key].id,
                    title=str(item["title"]),
                    stage=item["stage"],
                    status=item["status"],
                    due_date=due_date,
                    created_at=created_at,
                    completed_at=completed_at,
                )
            )
    return tasks


async def seed_demo(db: AsyncSession) -> dict[str, object]:
    users = build_users()
    franchisees = build_franchisees(users)
    points = build_points(franchisees)
    ingredients = build_ingredients()
    dishes = build_dishes()
    dish_ingredients = build_dish_ingredients(dishes, ingredients)
    user_points = build_user_points(users, points)
    stock_items = build_stock_items(points, ingredients)
    stock_movements = build_stock_movements(stock_items, users)
    orders = build_orders(points, dishes)
    franchisee_tasks = build_franchisee_tasks(franchisees)

    await _merge_entities(db, users.values())
    await _merge_entities(db, franchisees.values())
    await _merge_entities(db, points.values())
    await _merge_entities(db, ingredients.values())
    await _merge_entities(db, dishes.values())

    db.add_all(dish_ingredients)
    db.add_all(user_points)
    db.add_all(stock_items.values())
    await db.flush()

    db.add_all(stock_movements)
    db.add_all(orders)
    db.add_all(franchisee_tasks)
    await db.flush()

    return {
        "users": users,
        "franchisees": franchisees,
        "points": points,
        "ingredients": ingredients,
        "dishes": dishes,
        "orders": orders,
        "stock_items": stock_items,
        "stock_movements": stock_movements,
        "franchisee_tasks": franchisee_tasks,
    }


def print_summary(created: dict[str, object]) -> None:
    users: dict[str, User] = created["users"]  # type: ignore[assignment]
    franchisees: dict[str, Franchisee] = created["franchisees"]  # type: ignore[assignment]
    points: dict[str, Point] = created["points"]  # type: ignore[assignment]
    dishes: dict[str, Dish] = created["dishes"]  # type: ignore[assignment]
    ingredients: dict[str, Ingredient] = created["ingredients"]  # type: ignore[assignment]
    orders: list[Order] = created["orders"]  # type: ignore[assignment]
    tasks: list[FranchiseeTask] = created["franchisee_tasks"]  # type: ignore[assignment]
    movements: list[StockMovement] = created["stock_movements"]  # type: ignore[assignment]

    print("Demo seed completed.")
    print(f"Users: {len(users)}")
    for user in users.values():
        print(f"  - {user.role.value}: {user.email}")
    print(f"Franchisees: {len(franchisees)}")
    print(f"Points: {len(points)}")
    print(f"Ingredients: {len(ingredients)}")
    print(f"Dishes: {len(dishes)}")
    print(f"Orders: {len(orders)}")
    print(f"Franchisee tasks: {len(tasks)}")
    print(f"Stock movements: {len(movements)}")


async def main() -> None:
    ensure_root_path()
    async with SessionLocal() as db:
        await cleanup_owned_demo_graph(db)
        created = await seed_demo(db)
        await db.commit()
        print_summary(created)


if __name__ == "__main__":
    asyncio.run(main())
